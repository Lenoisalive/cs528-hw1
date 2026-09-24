"""Exact directed closeness centrality using single-threaded BFS."""

from collections import deque
from fractions import Fraction


def closeness_centrality(graph, direction='outgoing'):
    """Compute reachability-adjusted closeness for every node.

    With r reachable OTHER nodes and distance sum s, score =
    (r / (n - 1)) * (r / s). Isolated and singleton nodes score zero.
    Incoming mode traverses reversed edges to measure distances to the node.
    """
    if direction not in ('outgoing', 'incoming'):
        raise ValueError('Closeness direction must be outgoing or incoming')
    count = len(graph.names)
    if not count:
        raise ValueError('Closeness requires at least one page')
    adjacency = getattr(graph, direction)
    scores = {}
    reachable_counts = {}
    distance_sums = {}
    exact_scores = {}
    for source, name in enumerate(graph.names):
        distances = [-1] * count
        distances[source] = 0
        queue = deque([source])
        reachable = 0
        distance_sum = 0
        while queue:
            node = queue.popleft()
            next_distance = distances[node] + 1
            for neighbor in adjacency[node]:
                if distances[neighbor] == -1:
                    distances[neighbor] = next_distance
                    queue.append(neighbor)
                    reachable += 1
                    distance_sum += next_distance
        exact_scores[name] = (Fraction(reachable * reachable, (count - 1) * distance_sum)
                              if reachable else Fraction(0))
        scores[name] = float(exact_scores[name])
        reachable_counts[name] = reachable
        distance_sums[name] = distance_sum
    best_score = max(exact_scores.values())
    best_pages = sorted(name for name in graph.names if exact_scores[name] == best_score)
    return {
        'direction': direction,
        'normalization': 'reachable_fraction_times_inverse_mean_distance',
        'best_pages': best_pages,
        'best_score': float(best_score),
        'scores': scores,
        'reachable_counts': reachable_counts,
        'distance_sums': distance_sums,
    }
