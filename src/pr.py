"""Original iterative PageRank with the assignment's total-sum stopping rule."""

import math


def pagerank(graph, tolerance=0.005, max_iterations=1000):
    """Return scores and stopping diagnostics without dangling redistribution.

    All updates use the previous iteration. A satisfied total-sum criterion
    does not imply convergence of individual scores. No normalization is used.
    """
    if not math.isfinite(tolerance) or not 0 <= tolerance < 1:
        raise ValueError('PageRank tolerance must be finite and in [0, 1)')
    if isinstance(max_iterations, bool) or not isinstance(max_iterations, int) or max_iterations < 1:
        raise ValueError('PageRank max_iterations must be a positive integer')
    count = len(graph.names)
    if not count:
        raise ValueError('PageRank requires at least one page')
    scores = [1.0 / count] * count
    previous_total = math.fsum(scores)
    criterion_met = False
    for iteration in range(1, max_iterations + 1):
        updated = [0.15 / count] * count
        for source, targets in enumerate(graph.outgoing):
            if targets:
                contribution = 0.85 * scores[source] / len(targets)
                for target in targets:
                    updated[target] += contribution
        total = math.fsum(updated)
        relative_change = abs(total - previous_total) / previous_total
        scores = updated
        if relative_change <= tolerance:
            criterion_met = True
            break
        previous_total = total
    ranking = sorted(range(count), key=lambda node: (-scores[node], graph.names[node]))
    return {
        'scores': dict(zip(graph.names, scores)),
        'top_5': [{'page': graph.names[node], 'score': scores[node]} for node in ranking[:5]],
        'iterations': iteration,
        'total_score': total,
        'relative_total_change': relative_change,
        'sum_criterion_met': criterion_met,
        'stop_reason': 'sum_tolerance' if criterion_met else 'max_iterations',
        'tolerance': tolerance,
        'max_iterations': max_iterations,
    }
