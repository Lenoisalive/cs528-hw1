"""Deterministic tests independent of the generated assignment graph."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from src.graph import build_graph, load_local_graph
from src.stats import graph_statistics, summarize


def html(*targets):
    return ''.join(f'<a HREF="{target}">Link</a>' for target in targets)


class GraphTests(unittest.TestCase):
    def test_known_graph(self):
        pages = {'A.html': html('B.html', 'C.html'), 'B.html': html('C.html'),
                 'C.html': html('A.html'), 'D.html': ''}
        graph = build_graph(pages, pages.items())
        self.assertEqual(graph.names, list(pages))
        self.assertEqual(graph.outgoing, [[1, 2], [2], [0], []])
        self.assertEqual(graph.incoming, [[2], [0], [0, 1], []])
        result = graph_statistics(graph)
        for direction in ('incoming', 'outgoing'):
            for key, expected in {'mean': 1, 'median': 1, 'min': 0, 'max': 2,
                                  'p20': 0.6, 'p40': 1, 'p60': 1, 'p80': 1.4}.items():
                self.assertAlmostEqual(result[direction][key], expected)
        self.assertEqual(sum(map(len, graph.incoming)), graph.edge_count)
        self.assertEqual(sum(map(len, graph.outgoing)), graph.edge_count)

    def test_link_policies(self):
        pages = {'A.html': html('A.html', 'A.html', 'B.html', 'B.html',
                                'missing.html', 'https://example.com/') + '<a>No href</a>',
                 'B.html': ''}
        graph = build_graph(pages, reversed(list(pages.items())))
        self.assertEqual(graph.outgoing, [[0, 1], []])
        self.assertEqual(graph.incoming, [[0], [0]])
        self.assertEqual((graph.raw_links, graph.duplicate_links,
                          graph.invalid_links, graph.self_links), (6, 2, 2, 1))

    def test_single_isolated_page(self):
        graph = build_graph(['0.html'], [('0.html', '')])
        self.assertTrue(all(value == 0 for value in graph_statistics(graph)['incoming'].values()))

    def test_incomplete_input(self):
        with self.assertRaises(ValueError):
            build_graph(['A.html'], [])

    def test_local_files_and_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'B.html').write_text('', encoding='utf-8')
            (root / 'A.html').write_text(html('B.html'), encoding='utf-8')
            (root / 'ignored.txt').write_text('not a page', encoding='utf-8')
            self.assertEqual(load_local_graph(root).outgoing, [[1], []])
            output = root / 'results' / 'stats.json'
            run = subprocess.run([sys.executable, '-m', 'src.main', '--input-dir', tmp,
                                  '--output', str(output)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(output.read_text())['edges'], 1)

    def test_empty_missing_and_bad_encoding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(ValueError):
                load_local_graph(root)
            with self.assertRaises(ValueError):
                load_local_graph(root / 'missing')
            (root / 'bad.html').write_bytes(b'\xff')
            with self.assertRaises(UnicodeError):
                load_local_graph(root)


class StatisticsTests(unittest.TestCase):
    def test_unequal_degrees_and_odd_median(self):
        result = summarize([9, 0, 1, 2, 3])
        self.assertEqual(result['mean'], 3)
        self.assertEqual(result['median'], 2)
        self.assertAlmostEqual(result['p80'], 4.2)

    def test_single_value_and_empty(self):
        self.assertTrue(all(value == 7 for value in summarize([7]).values()))
        with self.assertRaises(ValueError):
            summarize([])


if __name__ == '__main__':
    unittest.main()
