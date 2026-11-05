import io
import json
import os
import unittest
from unittest.mock import patch
from src.models import DeepSeekModel


class AdapterTests(unittest.TestCase):
    @patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'test-only-not-a-key', 'DEEPSEEK_MODEL': 'deepseek-flash', 'DEEPSEEK_BASE_URL': 'https://api.deepseek.com'})
    def test_adapter_sends_observed_results_and_parses_next_action(self):
        decision = {'action': 'finish', 'arguments': {'status': 'needs_confirmation', 'suggested_slot': '2026-11-10T19:00'}, 'reason': 'requested slot is occupied'}
        body = {'choices': [{'message': {'content': json.dumps(decision)}}]}
        trace = [{'action': 'query_slots', 'result': {'available': ['2026-11-10T19:00']}}]
        with patch('urllib.request.urlopen', return_value=io.BytesIO(json.dumps(body).encode())) as transport:
            actual = DeepSeekModel().decide({'request_id': 'test'}, trace)
        self.assertEqual(actual, decision)
        sent = json.loads(transport.call_args[0][0].data.decode())
        self.assertEqual(json.loads(sent['messages'][1]['content'])['observed_steps'], trace)
        self.assertEqual(sent['thinking'], {'type': 'disabled'})
        self.assertNotIn('test-only-not-a-key', json.dumps(sent))

    @patch.dict(os.environ, {'DEEPSEEK_API_KEY': ''})
    def test_missing_key_is_explicit_failure(self):
        with self.assertRaises(ValueError):
            DeepSeekModel()
