# CS528 Homework 1

## 1. Overview

Generate simulated HTML pages and build a directed graph from their links.
Compute incoming/outgoing link statistics, PageRank, and closeness centrality.
Read local files or a public GCS bucket using only Python's standard library and single-threaded algorithms.

## 2. File Structure

```text
cs528-hw1/
├── src/
│   ├── generate.py
│   ├── graph.py
│   ├── gcs.py
│   ├── environment.py
│   ├── stats.py
│   ├── pr.py
│   ├── central_calc.py
│   └── main.py
├── tests/
│   ├── test_local.py
│   ├── test_pr.py
│   ├── test_gcs.py
│   └── test_centrality.py
├── data/
├── results/
├── report/
└── README.md
```

## 3. Link Statistics

[src/stats.py](src/stats.py) computes **Average, Median, Max, Min, and Quintiles**
for incoming and outgoing links across all pages, including zero-degree pages.
Quintiles are P20, P40, P60, and P80, using linear interpolation at `(n - 1) * p`.
Results appear in the terminal and in the JSON output's `incoming` and `outgoing`
fields; see [results/local_stats.json](results/local_stats.json) for an example.

## 4. Run

Use Python 3.8+ from the repository root; no dependency installation is needed.

```bash
python3 -m src.generate -n 12000 -m 325 --output-dir data/full
python3 -m src.main --input-dir data/full --pagerank --closeness --output results/full_analysis.json
```

For a fresh anonymous GCS run (no login or SDK required):

```bash
python3 -m src.main --bucket cs528hw2 --prefix pages/ --expected-files 12000 --pagerank --closeness --environment local --output results/local_gcs.json
```

Use the same bucket, prefix, commit, and algorithm parameters in all three
environments; change only the environment label and output path.

| Generator parameter | Meaning |
| --- | --- |
| `-n`, `--num_files` | Number of pages; default `10000`. |
| `-m`, `--max_refs` | Original client's link bound; default `250`. Its loop produces 0 through `m - 2` links, so `325` allows at most 323. |
| `--output-dir` | Destination directory; default current directory. Must contain no existing HTML files. |

| Analysis parameter | Meaning |
| --- | --- |
| `--input-dir` | Local HTML directory; use exactly one of this or `--bucket`. |
| `--bucket` | Public bucket name, without `gs://`. |
| `--prefix` | GCS directory prefix; default `pages/`. Empty string selects the root. |
| `--expected-files` | Optional expected HTML count; fail on mismatch. |
| `--environment` | Recorded experiment label, e.g. `local`, `cloudshell`, or `vm`. |
| `--output` | Optional JSON output path. |
| `--pagerank` | Enable PageRank and top 5 output. |
| `--pr-tolerance` | Relative PR-total change threshold; default `0.005` (0.5%). |
| `--pr-max-iterations` | Maximum PageRank iterations; default `1000`. |
| `--closeness` | Enable closeness centrality and output all highest-scoring pages. |
| `--closeness-direction` | `outgoing` (default): distances to other pages; `incoming`: distances from other pages. |

GCS reads immediate `.html` children of the prefix, follows every listing page,
and downloads each listed object generation sequentially. No local file cache
is used; requests ask caches to revalidate. Remote infrastructure caching cannot
be controlled. Transient HTTP/network errors are retried up to three times with
1/2/4-second delays and a 60-second socket timeout; permanent errors fail the run.
The bucket must allow anonymous object listing and reading.

JSON records OS, Python, CPU, visible system memory, commit, dirty-worktree state,
parameters, UTC start time, downloaded bytes, and a SHA-256 fingerprint of sorted
page names and contents. Compare fingerprints across environments. Unavailable
environment fields are null; record the VM machine type/zone separately.

GCS timings separate listing, download, UTF-8 decoding/HTML parsing/graph building,
fingerprinting, statistics, PageRank, closeness, and total processing time.
Download timing includes retries; parsing time is graph-loading wall time minus
download and fingerprint time. Total excludes environment collection, JSON output,
and terminal printing. Local reads retain the combined `read_parse_build` timing.

## 5. Test

```bash
python3 -m unittest discover -s tests -v
```

Tests use fixed small graphs and hand-computed expectations, independently of the random 12K dataset.
GCS tests use mocked API responses and require no network or cloud credentials.

## 6. Core Algorithms

**PageRank — [src/pr.py](src/pr.py):** Start every page at `1/N`, then update all
scores from the previous iteration:

```text
PR_new(A) = 0.15/N + 0.85 * sum(PR_old(T) / outgoing_degree(T) for T pointing to A)
```

Stop when `abs(new_total - old_total) / old_total <= 0.005`, or at the iteration
limit. Pages without outgoing links contribute nothing; scores are not normalized.
This required total-sum rule can stop before individual scores converge. Output the top 5 pages.

**Closeness — [src/central_calc.py](src/central_calc.py):** Run BFS from every page
along outgoing links to find shortest distances. For `r` reachable other pages
and distance sum `S`, use the reachability correction:

```text
C(u) = (r / (N - 1)) * (r / S)
```

Pages reaching no other pages score zero. Return all highest-scoring pages,
using exact fractions to detect ties and sorting their names. Runtime is
`O(V * (V + E))`.

Both algorithms use the graph built in [src/graph.py](src/graph.py): duplicate
links are collapsed, invalid targets are ignored, and self-links are retained.
