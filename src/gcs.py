"""Anonymous, sequential GCS JSON API reads without a local data cache."""

import hashlib
import json
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from .graph import build_graph


def fetch(url):
    """Retry transient errors three times; never send credentials."""
    for attempt in range(4):
        try:
            request = Request(url, headers={'Cache-Control': 'no-cache'})
            with urlopen(request, timeout=60) as response:
                return response.read()
        except HTTPError as error:
            if error.code not in (408, 429, 500, 502, 503, 504) or attempt == 3:
                raise OSError(f'GCS HTTP {error.code}: {url}') from error
        except (URLError, TimeoutError) as error:
            if attempt == 3:
                raise OSError(f'GCS request failed: {url}: {error}') from error
        time.sleep(2 ** attempt)


def load_gcs_graph(bucket, prefix='pages/', expected_files=None):
    """List immediate HTML children, pin generations, and stream into the graph."""
    if not bucket or any(char in bucket for char in '/:'):
        raise ValueError('Use a bucket name without gs:// or a path')
    prefix = prefix.rstrip('/') + '/' if prefix else ''
    base = f'https://storage.googleapis.com/storage/v1/b/{quote(bucket, safe="")}/o'
    started = time.perf_counter()
    print(f'Listing HTML objects in gs://{bucket}/{prefix} ...', file=sys.stderr, flush=True)
    objects = []
    token = None
    seen_tokens = set()
    while True:
        params = {'prefix': prefix, 'delimiter': '/', 'maxResults': 1000,
                  'fields': 'items(name,generation),nextPageToken'}
        if token:
            params['pageToken'] = token
        response = json.loads(fetch(base + '?' + urlencode(params)))
        for item in response.get('items', []):
            name = item['name']
            relative = name[len(prefix):]
            if name.startswith(prefix) and relative.endswith('.html') and '/' not in relative:
                objects.append((relative, name, item['generation']))
        token = response.get('nextPageToken')
        if not token:
            break
        if token in seen_tokens:
            raise ValueError('GCS returned a repeated page token')
        seen_tokens.add(token)
    objects.sort()
    if not objects:
        raise ValueError('No HTML pages found in GCS prefix')
    if expected_files is not None and len(objects) != expected_files:
        raise ValueError(f'Expected {expected_files} files, found {len(objects)}')
    listing_seconds = time.perf_counter() - started
    download_seconds = 0.0
    fingerprint_seconds = 0.0
    downloaded_bytes = 0
    fingerprint = hashlib.sha256()
    progress_seconds = 0.0
    print(f'Found {len(objects)} HTML files. Starting sequential download.', file=sys.stderr, flush=True)
    print(f'{"Completed":>15} {"Percent":>8} {"MiB":>10} {"Elapsed(s)":>12} {"Files/s":>10} {"ETA(s)":>12}',
          file=sys.stderr, flush=True)

    def pages():
        nonlocal download_seconds, fingerprint_seconds, downloaded_bytes, progress_seconds
        progress_started = time.perf_counter()
        last_report = progress_started
        for completed, (relative, name, generation) in enumerate(objects, 1):
            before = time.perf_counter()
            url = base + '/' + quote(name, safe='') + '?' + urlencode(
                {'alt': 'media', 'generation': generation})
            content = fetch(url)
            download_seconds += time.perf_counter() - before
            before = time.perf_counter()
            downloaded_bytes += len(content)
            fingerprint.update(json.dumps([relative, len(content)]).encode('utf-8'))
            fingerprint.update(b'\0')
            fingerprint.update(content)
            fingerprint_seconds += time.perf_counter() - before
            yield relative, content.decode('utf-8')
            now = time.perf_counter()
            if completed == 1 or completed % 100 == 0 or completed == len(objects) or now - last_report >= 30:
                elapsed = now - progress_started
                rate = completed / elapsed if elapsed > 0 else 0.0
                eta = (len(objects) - completed) / rate if rate else 0.0
                print(f'{completed:>7}/{len(objects):<7} {completed / len(objects):>7.1%} '
                      f'{downloaded_bytes / (1024 * 1024):>10.2f} {elapsed:>12.1f} '
                      f'{rate:>10.2f} {eta:>12.1f}', file=sys.stderr, flush=True)
                last_report = now
                progress_seconds += time.perf_counter() - now

    before = time.perf_counter()
    graph = build_graph((row[0] for row in objects), pages())
    parse_seconds = time.perf_counter() - before - download_seconds - fingerprint_seconds - progress_seconds
    print('Download and graph construction complete.', file=sys.stderr, flush=True)
    return graph, {
        'listing': listing_seconds,
        'download': download_seconds,
        'parse_build': max(0.0, parse_seconds),
        'fingerprint': fingerprint_seconds,
    }, {
        'type': 'gcs', 'bucket': bucket, 'prefix': prefix,
        'cache_policy': 'fresh anonymous requests; no local cache',
        'downloaded_bytes': downloaded_bytes,
        'dataset_sha256': fingerprint.hexdigest(),
        'object_count': len(objects),
    }
