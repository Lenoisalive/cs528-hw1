"""Hand-computed centrality tests independent of generated random graphs."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from src.central_calc import closeness_centrality
from src.graph import build_graph, Graph


def make_graph(links):
    pages = {name: ''.join(f'<a href="{target}">link</a>' for target in targets)
             for name, targets in links.items()}
    return build_graph(pages, pages.items())


class ClosenessTests(unittest.TestCase):
    def test_bidirectional_star(self):
        graph = make_graph({'A': ['B', 'C', 'D'], 'B': ['A'], 'C': ['A'], 'D': ['A']})
        result = closeness_centrality(graph)
        self.assertEqual(result['best_pages'], ['A'])
        self.assertEqual(result['best_score'], 1)
        for leaf in 'BCD':
            self.assertAlmostEqual(result['scores'][leaf], 3 / 5)
            self.assertEqual(result['distance_sums'][leaf], 5)

    def test_bidirectional_path(self):
        result = closeness_centrality(make_graph({'A': ['B'], 'B': ['A', 'C'], 'C': ['B']}))
        self.assertEqual(result['best_pages'], ['B'])
        self.assertEqual(result['scores']['B'], 1)
        self.assertAlmostEqual(result['scores']['A'], 2 / 3)
        self.assertAlmostEqual(result['scores']['C'], 2 / 3)

    def test_directed_path_and_reversal(self):
        graph = make_graph({'A': ['B'], 'B': ['C'], 'C': []})
        outgoing = closeness_centrality(graph)
        incoming = closeness_centrality(graph, 'incoming')
        self.assertEqual(outgoing['best_pages'], ['A'])
        self.assertEqual(incoming['best_pages'], ['C'])
        for name, expected in {'A': 2 / 3, 'B': 0.5, 'C': 0}.items():
            self.assertAlmostEqual(outgoing['scores'][name], expected)
        self.assertEqual(outgoing['scores']['A'], incoming['scores']['C'])
        self.assertEqual(outgoing['scores']['C'], incoming['scores']['A'])

    def test_disconnected_reachability_correction(self):
        result = closeness_centrality(make_graph({'A': ['B'], 'B': ['A'], 'C': []}))
        self.assertEqual(result['scores'], {'A': 0.5, 'B': 0.5, 'C': 0})
        self.assertEqual(result['best_pages'], ['A', 'B'])
        self.assertEqual(result['reachable_counts'], {'A': 1, 'B': 1, 'C': 0})

    def test_shortest_path_not_walk_count(self):
        graph = make_graph({'A': ['A', 'B', 'C', 'D'], 'B': ['D'], 'C': ['D'], 'D': ['A']})
        result = closeness_centrality(graph)
        self.assertEqual(result['reachable_counts']['A'], 3)
        self.assertEqual(result['distance_sums']['A'], 3)
        self.assertEqual(result['scores']['A'], 1)

    def test_singleton_and_all_isolated(self):
        for links in ({'A': []}, {'A': ['A']}, {'B': [], 'A': []}):
            result = closeness_centrality(make_graph(links))
            self.assertEqual(result['best_pages'], sorted(links))
            self.assertEqual(result['best_score'], 0)
            self.assertTrue(all(score == 0 for score in result['scores'].values()))

    def test_invalid_input(self):
        with self.assertRaises(ValueError):
            closeness_centrality(make_graph({'A': []}), 'undirected')
        with self.assertRaises(ValueError):
            closeness_centrality(Graph([], {}, [], []))

    def test_cli_with_pagerank(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'A.html').write_text('<a href="B.html">B</a>', encoding='utf-8')
            (root / 'B.html').write_text('', encoding='utf-8')
            output = root / 'result.json'
            run = subprocess.run(
                [sys.executable, '-m', 'src.main', '--input-dir', tmp, '--pagerank',
                 '--closeness', '--closeness-direction', 'incoming', '--output', str(output)],
                capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            result = json.loads(output.read_text())
            self.assertEqual(result['closeness']['best_pages'], ['B.html'])
            self.assertEqual(result['closeness']['best_score'], 1)
            self.assertIn('pagerank', result['timing_seconds'])
            self.assertIn('closeness', result['timing_seconds'])
            self.assertIn('Best pages by closeness: B.html', run.stdout)
            (root / 'B.html').write_text('<a href="A.html">A</a>', encoding='utf-8')
            tied = subprocess.run(
                [sys.executable, '-m', 'src.main', '--input-dir', tmp,
                 '--closeness', '--output', str(output)], capture_output=True, text=True)
            self.assertEqual(tied.returncode, 0, tied.stderr)
            result = json.loads(output.read_text())
            self.assertEqual(result['closeness']['direction'], 'outgoing')
            self.assertEqual(result['closeness']['best_pages'], ['A.html', 'B.html'])
            self.assertIn('Best pages by closeness: A.html, B.html', tied.stdout)


if __name__ == '__main__':
    unittest.main()
