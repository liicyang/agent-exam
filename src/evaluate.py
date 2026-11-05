"""Generate actual examples and check business outcomes; no invented traces."""
import argparse
import copy
import io
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from .agent import run_agent
from .models import DeepSeekModel, MockModel
from .tools import BusinessTools

CASES = [
    ('normal', 'M01', '19:00', False, None, 'saved'),
    ('missing_information', 'M02', '19:00', False, None, 'missing_information'),
    ('risk', 'M03', '19:00', False, None, 'blocked'),
    ('conflict', 'M01', '18:00', False, None, 'needs_confirmation'),
    ('save_failure', 'M01', '19:00', True, None, 'failed'),
    ('confirmed', 'M01', '18:00', False, '19:00', 'saved'),
    ('repeat', 'M01', '19:00', False, None, 'saved'),
    ('changed_occupancy', 'M01', '18:00', False, None, 'needs_confirmation'),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['mock', 'real'], default='mock')
    args = parser.parse_args()
    model = DeepSeekModel() if args.mode == 'real' else MockModel()
    root = Path('examples') / args.mode
    root.mkdir(parents=True, exist_ok=True)
    inputs = Path('examples/inputs')
    inputs.mkdir(parents=True, exist_ok=True)
    catalog = json.loads(Path('data/catalog.json').read_text(encoding='utf-8'))
    report = {'mode': args.mode, 'model': model.model, 'generated_at_utc': datetime.now(timezone.utc).isoformat(), 'cases': []}
    for name, material, hour, fail, confirmed, expected in CASES:
        request = {'request_id': name, 'material_id': material, 'requested_slot': '2026-11-10T' + hour}
        if confirmed:
            request['confirmed_slot'] = '2026-11-10T' + confirmed
        (inputs / (name + '.json')).write_text(json.dumps(request, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        case_catalog = copy.deepcopy(catalog)
        if name == 'changed_occupancy':
            case_catalog['occupied'].append('2026-11-10T19:00')
        with tempfile.TemporaryDirectory() as temp:
            tools = BusinessTools(case_catalog, request, Path(temp) / 'case.db', fail)
            try:
                result = run_agent(request, tools, model)
                if name == 'repeat':
                    (root / 'repeat_first.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
                    result = run_agent(request, tools, model)
                rows = tools.db.execute('SELECT COUNT(*) FROM drafts').fetchone()[0]
            finally:
                tools.close()
        result['fixture'] = {'catalog': case_catalog, 'fail_save': fail, 'draft_count': rows}
        (root / (name + '.json')).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        passed = result['status'] == expected and not result['published']
        passed = passed and rows == (1 if expected == 'saved' else 0)
        if name == 'repeat':
            passed = passed and bool((result.get('draft') or {}).get('duplicate'))
        if name in ('conflict', 'changed_occupancy'):
            passed = passed and result['suggested_slot'] == ('2026-11-10T20:00' if name == 'changed_occupancy' else '2026-11-10T19:00')
        report['cases'].append({'name': name, 'expected': expected, 'actual': result['status'], 'passed': passed, 'record': name + '.json'})
        print(name + ': ' + ('PASS' if passed else 'FAIL'), flush=True)
    report['passed'] = all(c['passed'] for c in report['cases'])
    (root / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if args.mode == 'mock':
        stream = io.StringIO()
        test_result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.discover('tests'))
        (root / 'tests.txt').write_text(stream.getvalue(), encoding='utf-8')
        report['passed'] = report['passed'] and test_result.wasSuccessful()
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
