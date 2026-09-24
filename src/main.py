"""Read local HTML pages and report incoming and outgoing link statistics."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from .graph import load_local_graph
from .stats import graph_statistics
from .pr import pagerank
from .central_calc import closeness_centrality
from .gcs import load_gcs_graph
from .environment import environment_info


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--input-dir', type=Path, help='Directory containing *.html pages')
    source.add_argument('--bucket', help='Public GCS bucket name without gs://')
    parser.add_argument('--prefix', default='pages/', help='GCS directory prefix (default: pages/)')
    parser.add_argument('--expected-files', type=int, help='Fail if the HTML file count differs')
    parser.add_argument('--download-workers', type=int, default=1,
                        help='GCS download threads only; default: 1 (sequential)')
    parser.add_argument('--environment', default='unspecified', help='Experiment label, e.g. local/cloudshell/vm')
    parser.add_argument('--output', type=Path, help='Optional JSON results file')
    parser.add_argument('--pagerank', action='store_true', help='Compute original iterative PageRank')
    parser.add_argument('--pr-tolerance', type=float, default=0.005,
                        help='Relative total-score change threshold (default: 0.005)')
    parser.add_argument('--pr-max-iterations', type=int, default=1000,
                        help='Maximum PageRank iterations (default: 1000)')
    parser.add_argument('--closeness', action='store_true', help='Compute exact closeness centrality')
    parser.add_argument('--closeness-direction', choices=('outgoing', 'incoming'),
                        default='outgoing', help='Distance direction (default: outgoing)')
    args = parser.parse_args()
    if args.download_workers < 1:
        parser.error('--download-workers must be positive')
    if args.expected_files is not None and args.expected_files < 1:
        parser.error('--expected-files must be positive')
    environment = environment_info(args.environment)
    run_started = datetime.now(timezone.utc).isoformat()
    try:
        started = perf_counter()
        if args.bucket:
            graph, input_timings, input_info = load_gcs_graph(
                args.bucket, args.prefix, args.expected_files, args.download_workers)
        else:
            graph = load_local_graph(args.input_dir)
            input_timings = {'read_parse_build': perf_counter() - started}
            input_info = {'type': 'local', 'path': str(args.input_dir)}
            if args.expected_files is not None and len(graph.names) != args.expected_files:
                raise ValueError(f'Expected {args.expected_files} files, found {len(graph.names)}')
        loaded = perf_counter()
        result = graph_statistics(graph)
        stats_finished = perf_counter()
        if args.pagerank:
            result['pagerank'] = pagerank(graph, args.pr_tolerance, args.pr_max_iterations)
        pr_finished = perf_counter()
        if args.closeness:
            result['closeness'] = closeness_centrality(graph, args.closeness_direction)
        finished = perf_counter()
        result['timing_seconds'] = {
            **input_timings,
            'statistics': stats_finished - loaded,
            'total': finished - started,
        }
        if args.pagerank:
            result['timing_seconds']['pagerank'] = pr_finished - stats_finished
        if args.closeness:
            result['timing_seconds']['closeness'] = finished - pr_finished
        result['environment'] = environment
        result['input'] = input_info
        result['started_at_utc'] = run_started
        result['parameters'] = {key: str(value) if isinstance(value, Path) else value
                                for key, value in vars(args).items()}
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    except (OSError, UnicodeError, ValueError) as error:
        parser.exit(1, f'Error: {error}\n')
    for key in ('pages', 'edges', 'raw_links', 'duplicate_links', 'invalid_links', 'self_links'):
        print(f'{key}: {result[key]}')
    print(f'\n{"Metric":<12}{"Incoming":>14}{"Outgoing":>14}')
    for metric in ('mean', 'median', 'max', 'min', 'p20', 'p40', 'p60', 'p80'):
        print(f'{metric:<12}{result["incoming"][metric]:>14.4f}{result["outgoing"][metric]:>14.4f}')
    for stage, seconds in input_timings.items():
        print(f'{stage}: {seconds:.6f} seconds')
    print(f'Statistics: {stats_finished - loaded:.6f} seconds')
    if args.pagerank:
        pr = result['pagerank']
        print('\nTop pages by PageRank:')
        for rank, page in enumerate(pr['top_5'], 1):
            print(f'{rank}. {page["page"]}: {page["score"]:.12g}')
        print(f'Iterations: {pr["iterations"]}')
        print(f'Total PageRank: {pr["total_score"]:.12g}')
        print(f'Relative total change: {pr["relative_total_change"]:.6%}')
        print(f'Stop reason: {pr["stop_reason"]}')
        print(f'PageRank: {pr_finished - stats_finished:.6f} seconds')
    if args.closeness:
        centrality = result['closeness']
        print(f'\nCloseness direction: {centrality["direction"]}')
        print(f'Best pages by closeness: {", ".join(centrality["best_pages"])}')
        print(f'Closeness score: {centrality["best_score"]:.12g}')
        print(f'Closeness: {finished - pr_finished:.6f} seconds')
    print(f'Total: {finished - started:.6f} seconds')


if __name__ == '__main__':
    main()
