"""Hand-derived PageRank cases independent of randomly generated pages."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from src.graph import build_graph
from src.pr import pagerank


def make_graph(links):
    pages = {name: ''.join(f'<a href="{target}">link</a>' for target in targets)
             for name, targets in links.items()}
    return build_graph(pages, pages.items())


class PageRankTests(unittest.TestCase):
    def test_symmetric_cycle(self):
        result = pagerank(make_graph({'A': ['B'], 'B': ['C'], 'C': ['A']}))
        for score in result['scores'].values():
            self.assertAlmostEqual(score, 1 / 3)
        self.assertEqual(result['iterations'], 1)
        self.assertEqual(result['stop_reason'], 'sum_tolerance')

    def test_asymmetric_first_round_and_early_stop(self):
        # With no dangling pages the total remains 1, despite unequal scores.
        result = pagerank(make_graph({'A': ['B', 'C'], 'B': ['C'], 'C': ['A']}))
        expected = {'A': 1 / 3, 'B': 23 / 120, 'C': 19 / 40}
        for name, score in expected.items():
            self.assertAlmostEqual(result['scores'][name], score)
        self.assertAlmostEqual(result['total_score'], 1)
        self.assertEqual(result['iterations'], 1)
        self.assertEqual([row['page'] for row in result['top_5']], ['C', 'A', 'B'])

    def test_dangling_chain(self):
        # Iterations: (.075,.5), (.075,.13875), then unchanged.
        result = pagerank(make_graph({'A': ['B'], 'B': []}))
        self.assertEqual(result['iterations'], 3)
        self.assertAlmostEqual(result['scores']['A'], 0.075)
        self.assertAlmostEqual(result['scores']['B'], 0.13875)
        self.assertAlmostEqual(result['total_score'], 0.21375)
        self.assertEqual(result['relative_total_change'], 0)
        self.assertTrue(result['sum_criterion_met'])

    def test_iteration_limit(self):
        result = pagerank(make_graph({'A': ['B'], 'B': []}), max_iterations=1)
        self.assertEqual(result['iterations'], 1)
        self.assertEqual(result['stop_reason'], 'max_iterations')
        self.assertFalse(result['sum_criterion_met'])
        self.assertAlmostEqual(result['scores']['B'], 0.5)
        self.assertAlmostEqual(result['relative_total_change'], 0.425)

    def test_relative_not_absolute_change(self):
        # Round 2: absolute change .36125, relative change .36125/.575 > .4.
        result = pagerank(make_graph({'A': ['B'], 'B': []}), tolerance=0.4)
        self.assertEqual(result['iterations'], 3)

    def test_all_dangling_and_top_five_ties(self):
        result = pagerank(make_graph({name: [] for name in 'GFEDCBA'}))
        self.assertEqual(result['iterations'], 2)
        self.assertEqual([row['page'] for row in result['top_5']], list('ABCDE'))
        for score in result['scores'].values():
            self.assertAlmostEqual(score, 0.15 / 7)

    def test_single_self_link(self):
        result = pagerank(make_graph({'A': ['A']}))
        self.assertEqual(result['scores'], {'A': 1.0})
        self.assertEqual(len(result['top_5']), 1)

    def test_invalid_parameters(self):
        graph = make_graph({'A': []})
        for tolerance in (-1, 1, float('nan'), float('inf')):
            with self.subTest(tolerance=tolerance), self.assertRaises(ValueError):
                pagerank(graph, tolerance=tolerance)
        for limit in (0, -1, 1.5, True):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                pagerank(graph, max_iterations=limit)

    def test_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'A.html').write_text('<a href="B.html">B</a>', encoding='utf-8')
            (root / 'B.html').write_text('', encoding='utf-8')
            output = root / 'result.json'
            command = [sys.executable, '-m', 'src.main', '--input-dir', tmp,
                       '--pagerank', '--output', str(output)]
            run = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            result = json.loads(output.read_text())
            self.assertEqual(result['pagerank']['iterations'], 3)
            self.assertIn('pagerank', result['timing_seconds'])
            self.assertIn('Stop reason: sum_tolerance', run.stdout)
            invalid = subprocess.run(command + ['--pr-max-iterations', '0'],
                                     capture_output=True, text=True)
            self.assertNotEqual(invalid.returncode, 0)
            self.assertIn('positive integer', invalid.stderr)


if __name__ == '__main__':
    unittest.main()
