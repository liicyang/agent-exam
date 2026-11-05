"""Bounded model -> tool -> observation loop; authoritative output from evidence."""
from datetime import datetime


def validate_request(request):
    if not isinstance(request, dict):
        return ['request_object']
    missing = [k for k in ('request_id', 'material_id', 'requested_slot') if not isinstance(request.get(k), str) or not request[k].strip()]
    for key in ('requested_slot', 'confirmed_slot'):
        if request.get(key):
            try:
                datetime.strptime(request[key], '%Y-%m-%dT%H:%M')
            except (ValueError, TypeError):
                missing.append(key + '_invalid_datetime')
    return missing


def run_agent(request, tools, model, max_steps=10):
    trace = []
    result = {'mode': model.mode, 'model': model.model, 'request': request, 'status': 'incomplete', 'review_status': 'not_checked', 'risk_reasons': [], 'pending_items': [], 'suggested_slot': None, 'save_status': 'not_saved', 'draft': None, 'published': False, 'trace': trace}
    missing = validate_request(request)
    if missing:
        result.update(status='missing_information', pending_items=missing, stop_reason='invalid_request')
        return result
    for index in range(max_steps):
        try:
            decision = model.decide(request, trace)
            if not isinstance(decision, dict) or not isinstance(decision.get('action'), str) or not isinstance(decision.get('arguments'), dict) or not isinstance(decision.get('reason'), str):
                raise ValueError('invalid decision schema')
        except Exception as exc:
            # Never include exception text, HTTP response, or credentials in trace.
            result.update(status='failed', stop_reason='model_error', error_type=type(exc).__name__)
            return result
        action, args = decision['action'], decision['arguments']
        entry = {'step': index + 1, 'action': action, 'arguments': args, 'reason': decision['reason']}
        trace.append(entry)
        if action == 'finish':
            observed = {t['action']: t.get('result', {}) for t in trace[:-1]}
            review = observed.get('check_rules', {})
            saved = observed.get('save_draft', {})
            if saved.get('ok'):
                result['status'] = 'saved'
            elif review.get('status') in ('missing_information', 'blocked'):
                result['status'] = review['status']
            elif saved and not saved.get('ok'):
                result['status'] = 'failed'
            elif args.get('status') == 'needs_confirmation' and review.get('status') == 'approved' and args.get('suggested_slot') in observed.get('query_slots', {}).get('available', []):
                result.update(status='needs_confirmation', suggested_slot=args['suggested_slot'], pending_items=['请确认替代时段；尚未保存草稿'])
            else:
                result['status'] = 'incomplete'
            result['stop_reason'] = 'model_finished'
            return result
        # Guard saves even when the model skips required observations.
        prior = {t['action']: t.get('result', {}) for t in trace[:-1]}
        if action == 'save_draft' and not all(k in prior for k in ('read_material', 'check_rules', 'query_slots')):
            observation = {'ok': False, 'error': 'required_checks_missing'}
        else:
            observation = tools.execute(action, args)
        entry['result'] = observation
        if action == 'check_rules' and observation.get('ok'):
            result.update(review_status=observation['status'], risk_reasons=observation['risks'], pending_items=observation['missing'])
        if action == 'save_draft':
            result['save_status'] = 'saved' if observation.get('ok') else 'failed'
            if observation.get('ok'):
                result.update(draft=observation, suggested_slot=observation['slot'])
    result['stop_reason'] = 'step_limit_reached'
    return result
