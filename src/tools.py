"""Trusted business tools. Model proposals never bypass these checks."""
import hashlib
import json
import sqlite3


class BusinessTools:
    def __init__(self, catalog, request, db_path, fail_save=False):
        self.catalog, self.request = catalog, request
        self.fail_save = fail_save
        self.db = sqlite3.connect(str(db_path), timeout=10)
        self.db.execute('CREATE TABLE IF NOT EXISTS drafts (id TEXT PRIMARY KEY, request_id TEXT UNIQUE, fingerprint TEXT, material_id TEXT, slot TEXT UNIQUE)')
        self.db.commit()

    def close(self):
        self.db.close()

    def read_material(self):
        material = self.catalog['materials'].get(self.request['material_id'])
        return {'ok': material is not None, 'material': material, 'error': None if material else 'material_not_found'}

    def check_rules(self):
        material = self.catalog['materials'].get(self.request['material_id'], {})
        rules = self.catalog['rules']
        missing = [key for key in rules['required'] if not material.get(key)]
        risks = [key + '_not_approved' for key in ('rights', 'review') if material.get(key) and material[key] != rules[key]]
        return {'ok': True, 'status': 'missing_information' if missing else ('blocked' if risks else 'approved'), 'missing': missing, 'risks': risks}

    def query_slots(self):
        busy = set(self.catalog['occupied'])
        busy.update(row[0] for row in self.db.execute('SELECT slot FROM drafts WHERE request_id != ?', (self.request['request_id'],)))
        return {'ok': True, 'available': [s for s in self.catalog['slots'] if s not in busy], 'occupied': sorted(busy), 'requested': self.request['requested_slot']}

    def save_draft(self, slot):
        if self.check_rules()['status'] != 'approved':
            return {'ok': False, 'error': 'review_not_approved'}
        # Confirmation originates in the CLI input, never in model arguments.
        if slot != self.request['requested_slot'] and slot != self.request.get('confirmed_slot'):
            return {'ok': False, 'error': 'confirmation_required'}
        fingerprint = hashlib.sha256(json.dumps(self.request, sort_keys=True).encode()).hexdigest()
        try:
            self.db.execute('BEGIN IMMEDIATE')
            existing = self.db.execute('SELECT id, fingerprint, slot FROM drafts WHERE request_id = ?', (self.request['request_id'],)).fetchone()
            if existing:
                self.db.rollback()
                if existing[1] != fingerprint or existing[2] != slot:
                    return {'ok': False, 'error': 'idempotency_conflict'}
                return {'ok': True, 'draft_id': existing[0], 'slot': existing[2], 'duplicate': True}
            if slot not in self.query_slots()['available']:
                self.db.rollback()
                return {'ok': False, 'error': 'slot_unavailable'}
            if self.fail_save:
                self.db.rollback()
                return {'ok': False, 'error': 'simulated_storage_failure'}
            draft_id = 'draft-' + hashlib.sha256(self.request['request_id'].encode()).hexdigest()[:16]
            self.db.execute('INSERT INTO drafts VALUES (?, ?, ?, ?, ?)', (draft_id, self.request['request_id'], fingerprint, self.request['material_id'], slot))
            self.db.commit()
            return {'ok': True, 'draft_id': draft_id, 'slot': slot, 'duplicate': False}
        except sqlite3.Error:
            self.db.rollback()
            return {'ok': False, 'error': 'storage_failure'}

    def execute(self, action, arguments):
        if not isinstance(arguments, dict):
            return {'ok': False, 'error': 'arguments_must_be_object'}
        if action in ('read_material', 'check_rules', 'query_slots') and not arguments:
            return getattr(self, action)()
        if action == 'save_draft' and set(arguments) == {'slot'} and isinstance(arguments['slot'], str):
            return self.save_draft(arguments['slot'])
        return {'ok': False, 'error': 'invalid_tool_or_arguments'}
