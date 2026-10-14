import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ahat_benchmark import cli
from helpers import FakeClient, PROJECT


class CliIntegrationTests(unittest.TestCase):
    def test_custom_registry_runs_all_stages_with_explicit_judge_configuration(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            context = ['--registry', str(PROJECT / 'examples/datasets.yaml')]
            common = ['--dataset', 'demo', '--inference', str(PROJECT / 'examples/inference.json'),
                      '--output-dir', str(directory), '--workers', '2']
            client = FakeClient()
            with patch.dict(os.environ, {'INF_API_KEY': 'test-key'}, clear=True), \
                 patch('ahat_benchmark.cli.load_dotenv'), \
                 patch('ahat_benchmark.cli.OpenAI', return_value=client) as constructor, \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main(context + ['val'] + common), 0)
                self.assertEqual(cli.main(context + ['judge'] + common + [
                    '--base-url', 'https://judge.example/v1', '--model', 'test-judge',
                    '--dimension-workers', '1']), 0)
                self.assertEqual(cli.main(context + ['summarize'] + common), 0)
            self.assertEqual(constructor.call_args.kwargs['base_url'], 'https://judge.example/v1')
            self.assertEqual(len(client.calls), 4)
            result = json.loads((directory / 'final_results.json').read_text())
            self.assertTrue(result['statistics']['publishable'])
            self.assertEqual(result['statistics']['final_score'], 0.5)

    def test_missing_endpoint_fails_before_client_creation(self):
        with tempfile.TemporaryDirectory() as temp, \
             patch.dict(os.environ, {'INF_API_KEY': 'test-key'}, clear=True), \
             patch('ahat_benchmark.cli.load_dotenv'), \
             patch('ahat_benchmark.cli.OpenAI') as constructor, \
             contextlib.redirect_stderr(io.StringIO()) as error:
            result = cli.main(['judge', '--dataset', 'ahat-easy', '--inference', 'unused.json',
                               '--output-dir', temp])
        self.assertEqual(result, 2)
        constructor.assert_not_called()
        self.assertIn('missing judge endpoint', error.getvalue())
