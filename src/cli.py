import argparse
import json
import sys
from pathlib import Path
from .agent import run_agent
from .models import DeepSeekModel, MockModel
from .tools import BusinessTools


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description='素材审核与排期草稿 Agent')
    parser.add_argument('--input', required=True)
    parser.add_argument('--mode', choices=['mock', 'real'], default='mock')
    parser.add_argument('--db', default='drafts.db')
    parser.add_argument('--catalog', default='data/catalog.json')
    parser.add_argument('--output')
    parser.add_argument('--max-steps', type=int, default=10)
    parser.add_argument('--fail-save', action='store_true', help='Inject a storage failure for testing')
    args = parser.parse_args()
    if not 1 <= args.max_steps <= 30:
        parser.error('--max-steps must be between 1 and 30')
    request = json.loads(Path(args.input).read_text(encoding='utf-8-sig'))
    catalog = json.loads(Path(args.catalog).read_text(encoding='utf-8-sig'))
    try:
        model = DeepSeekModel() if args.mode == 'real' else MockModel()
    except ValueError as exc:
        parser.error(str(exc))
    tools = BusinessTools(catalog, request, args.db, args.fail_save)
    try:
        result = run_agent(request, tools, model, args.max_steps)
    finally:
        tools.close()
    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(output + '\n', encoding='utf-8')
    print(output)
    return 1 if result['status'] in ('failed', 'incomplete') else 0


if __name__ == '__main__':
    raise SystemExit(main())
