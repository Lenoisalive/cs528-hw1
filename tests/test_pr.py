"""Hand-derived PageRank cases independent of randomly generated pages."""

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

if __name__ == '__main__':
    unittest.main()
