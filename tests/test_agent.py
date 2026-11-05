import copy
import json
import tempfile
import unittest
from pathlib import Path
from src.agent import run_agent
from src.models import MockModel
from src.tools import BusinessTools


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.catalog = json.loads(Path('data/catalog.json').read_text(encoding='utf-8'))
        self.request = {'request_id': 'test', 'material_id': 'M01', 'requested_slot': '2026-11-10T19:00'}
        self.tools = BusinessTools(self.catalog, self.request, Path(self.temp.name) / 'test.db')

    def tearDown(self):
        self.tools.close()
        self.temp.cleanup()

    def run_case(self, max_steps=10):
        return run_agent(self.request, self.tools, MockModel(), max_steps)

    def test_normal(self):
        result = self.run_case()
        self.assertEqual(result['status'], 'saved')
        self.assertFalse(result['published'])
        self.assertEqual(result['draft']['slot'], self.request['requested_slot'])

    def test_missing_metadata(self):
        self.request['material_id'] = 'M02'
        result = self.run_case()
        self.assertEqual(result['status'], 'missing_information')
        self.assertIn('rights', result['pending_items'])
        self.assertIsNone(result['draft'])

    def test_risk_blocks_save_even_if_called_directly(self):
        self.request['material_id'] = 'M03'
        self.assertEqual(self.run_case()['status'], 'blocked')
        self.assertFalse(self.tools.save_draft(self.request['requested_slot'])['ok'])

    def test_conflict_requires_confirmation(self):
        self.request['requested_slot'] = '2026-11-10T18:00'
        result = self.run_case()
        self.assertEqual(result['status'], 'needs_confirmation')
        self.assertEqual(result['suggested_slot'], '2026-11-10T19:00')
        self.assertEqual(self.tools.save_draft(result['suggested_slot'])['error'], 'confirmation_required')

    def test_user_confirmation(self):
        self.request.update(requested_slot='2026-11-10T18:00', confirmed_slot='2026-11-10T19:00')
        self.assertEqual(self.run_case()['status'], 'saved')

    def test_repeat_has_one_row(self):
        first, second = self.run_case(), self.run_case()
        self.assertEqual(first['draft']['draft_id'], second['draft']['draft_id'])
        self.assertTrue(second['draft']['duplicate'])
        self.assertEqual(self.tools.db.execute('SELECT COUNT(*) FROM drafts').fetchone()[0], 1)

    def test_changed_request_same_id_rejected(self):
        self.run_case()
        self.request['requested_slot'] = '2026-11-10T20:00'
        self.assertEqual(self.run_case()['trace'][-2]['result']['error'], 'idempotency_conflict')

    def test_storage_failure(self):
        self.tools.fail_save = True
        result = self.run_case()
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['save_status'], 'failed')
        self.assertEqual(self.tools.db.execute('SELECT COUNT(*) FROM drafts').fetchone()[0], 0)

    def test_changed_occupancy_changes_suggestion(self):
        self.request['requested_slot'] = '2026-11-10T18:00'
        self.catalog['occupied'].append('2026-11-10T19:00')
        self.assertEqual(self.run_case()['suggested_slot'], '2026-11-10T20:00')

    def test_no_available_slots(self):
        self.catalog['occupied'] = self.catalog['slots'][:]
        self.assertEqual(self.run_case()['status'], 'incomplete')

    def test_limit(self):
        result = self.run_case(1)
        self.assertEqual(result['stop_reason'], 'step_limit_reached')
        self.assertEqual(result['status'], 'incomplete')

    def test_missing_request_field(self):
        del self.request['requested_slot']
        self.assertEqual(self.run_case()['status'], 'missing_information')

    def test_unknown_material(self):
        self.request['material_id'] = 'DOES_NOT_EXIST'
        self.assertEqual(self.run_case()['status'], 'missing_information')

    def test_fabricated_success_is_not_trusted(self):
        class Liar(MockModel):
            def decide(self, request, trace):
                return {'action': 'finish', 'arguments': {'status': 'saved'}, 'reason': 'claimed success'}
        result = run_agent(self.request, self.tools, Liar())
        self.assertEqual(result['status'], 'incomplete')
        self.assertIsNone(result['draft'])

    def test_model_error_is_sanitized(self):
        class Broken(MockModel):
            def decide(self, request, trace):
                raise ValueError('secret-token')
        result = run_agent(self.request, self.tools, Broken())
        self.assertEqual(result['status'], 'failed')
        self.assertNotIn('secret-token', json.dumps(result))

    def test_two_requests_cannot_reserve_same_slot(self):
        self.run_case()
        another = copy.deepcopy(self.request)
        another['request_id'] = 'another'
        other_tools = BusinessTools(self.catalog, another, Path(self.temp.name) / 'test.db')
        try:
            self.assertEqual(other_tools.save_draft(another['requested_slot'])['error'], 'slot_unavailable')
        finally:
            other_tools.close()


if __name__ == '__main__':
    unittest.main()
