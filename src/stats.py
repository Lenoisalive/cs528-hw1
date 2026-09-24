"""Degree summaries with linear-interpolated quintile boundaries."""

import math


def percentile(sorted_values, p):
    """Interpolate at (n - 1) * p in an ascending, nonempty sequence."""
    if not sorted_values or not 0 <= p <= 1:
        raise ValueError('Percentile requires values and a probability in [0, 1]')
    position = (len(sorted_values) - 1) * p
    lower = math.floor(position)
    upper = math.ceil(position)
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * (position - lower)


def summarize(values):
    values = sorted(values)
    if not values:
        raise ValueError('Cannot summarize an empty dataset')
    return {
        'mean': sum(values) / len(values),
        'median': percentile(values, 0.5),
        'max': values[-1],
        'min': values[0],
        **{f'p{p}': percentile(values, p / 100) for p in (20, 40, 60, 80)},
    }


def graph_statistics(graph):
    return {
        'pages': len(graph.names),
        'edges': graph.edge_count,
        'raw_links': graph.raw_links,
        'duplicate_links': graph.duplicate_links,
        'invalid_links': graph.invalid_links,
        'self_links': graph.self_links,
        'incoming': summarize(len(edges) for edges in graph.incoming),
        'outgoing': summarize(len(edges) for edges in graph.outgoing),
    }
