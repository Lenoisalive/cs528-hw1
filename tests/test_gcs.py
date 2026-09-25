"""Offline GCS contract tests using fixed API responses."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from src.gcs import load_gcs_graph
from src.main import main


def listing(items, token=None):
    result = {'items': [{'name': name, 'generation': '123'} for name in items]}
    if token:
        result['nextPageToken'] = token
    return json.dumps(result).encode()


class GCSTests(unittest.TestCase):
    def test_pagination_names_graph_and_fingerprint(self):
        responses = [listing(['pages/B.html', 'pages/readme.txt'], 'a+b'),
                     listing([], 'next'), listing(['pages/A.html', 'pages/sub/C.html']),
                     b'<a href="B.html">B</a>', b'']
        with patch('src.gcs.fetch', side_effect=responses) as request:
            graph, timing, source = load_gcs_graph('test-bucket', 'pages', 2)
        self.assertEqual(graph.names, ['A.html', 'B.html'])
        self.assertEqual(graph.outgoing, [[1], []])
        calls = [call.args[0] for call in request.call_args_list]
        self.assertEqual(parse_qs(urlsplit(calls[1]).query)['pageToken'], ['a+b'])
        self.assertIn('pages%2FA.html', calls[3])
        self.assertEqual(parse_qs(urlsplit(calls[3]).query)['generation'], ['123'])
        self.assertTrue(all(value >= 0 for value in timing.values()))
        self.assertEqual(source['object_count'], 2)
        with patch('src.gcs.fetch', side_effect=responses):
            self.assertEqual(load_gcs_graph('test-bucket')[2]['dataset_sha256'], source['dataset_sha256'])
        with patch('src.gcs.fetch', side_effect=responses[:-1] + [b'changed']):
            self.assertNotEqual(load_gcs_graph('test-bucket')[2]['dataset_sha256'], source['dataset_sha256'])

    def test_cli_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'run.json'
            args = ['main', '--bucket', 'test-bucket', '--expected-files', '2', '--environment', 'local', '--output', str(output)]
            with patch('sys.argv', args), patch('src.gcs.fetch', side_effect=[
                listing(['pages/A.html', 'pages/B.html']), b'<a href="B.html">B</a>', b'']), \
                    contextlib.redirect_stdout(io.StringIO()):
                main()
            result = json.loads(output.read_text())
            self.assertEqual(result['pages'], 2)
            self.assertEqual(result['pagerank']['tolerance'], 0.005)
            self.assertEqual(result['pagerank']['max_iterations'], 1000)
            self.assertEqual(result['closeness']['direction'], 'outgoing')
            self.assertEqual(result['environment']['label'], 'local')
            self.assertIn('git_commit', result['environment'])
            self.assertEqual(result['pagerank']['iterations'], 3)
            self.assertEqual(result['closeness']['best_pages'], ['A.html'])
            timing = result['timing_seconds']
            for key in ('listing', 'download', 'parse_build', 'statistics', 'pagerank', 'closeness', 'total'):
                self.assertGreaterEqual(timing[key], 0)
            self.assertGreaterEqual(timing['total'] + 1e-6,
                                    sum(value for key, value in timing.items() if key != 'total'))


if __name__ == '__main__':
    unittest.main()
