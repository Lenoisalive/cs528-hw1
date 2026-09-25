"""Deterministic tests independent of the generated assignment graph."""

from pathlib import Path
import subprocess
import json
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

    def test_local_files_and_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'B.html').write_text('', encoding='utf-8')
            (root / 'A.html').write_text(html('B.html'), encoding='utf-8')
            (root / 'ignored.txt').write_text('not a page', encoding='utf-8')
            self.assertEqual(load_local_graph(root).outgoing, [[1], []])
            run = subprocess.run([sys.executable, '-m', 'src.main', '--input-dir', tmp],
                                 capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertIn('Top pages by PageRank:', run.stdout)
            output = root / 'result.json'
            run = subprocess.run([sys.executable, '-m', 'src.main', '--input-dir', tmp,
                                  '--expected-files', '2', '--output', str(output)],
                                 capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(output.read_text())['pages'], 2)
            mismatch = subprocess.run([sys.executable, '-m', 'src.main', '--input-dir', tmp,
                                       '--expected-files', '12000'], capture_output=True, text=True)
            self.assertNotEqual(mismatch.returncode, 0)
            self.assertIn('Expected 12000 files, found 2', mismatch.stderr)

class StatisticsTests(unittest.TestCase):
    def test_unequal_degrees_and_odd_median(self):
        result = summarize([9, 0, 1, 2, 3])
        self.assertEqual(result['mean'], 3)
        self.assertEqual(result['median'], 2)
        self.assertAlmostEqual(result['p80'], 4.2)

if __name__ == '__main__':
    unittest.main()
