"""Hand-computed centrality tests independent of generated random graphs."""

import unittest

from src.central_calc import closeness_centrality
from src.graph import build_graph


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

if __name__ == '__main__':
    unittest.main()
