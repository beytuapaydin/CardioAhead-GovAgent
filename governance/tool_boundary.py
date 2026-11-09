"""Sandbox-only action gateway. Policy is enforced at the tool boundary, not by an LLM.

IMPORTANT: A credential in this demo is NOT equivalent to an enterprise identity.
There is no access path to real clinical systems and no executable arbitrary shell tool.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from governance.audit import append_event, verify_chain
from governance.review import load_cases

SAFE_TOOLS = frozenset({'write_sandbox_note', 'export_sandbox_summary'})
DENIED_TOOLS = frozenset({'modify_clinical_threshold', 'override_physician_flag',
                          'edit_patient_record', 'execute_shell', 'change_permissions'})
ROLE_PERMISSIONS = {
    'viewer': frozenset(),
    'reviewer': frozenset({'write_sandbox_note'}),
    'operator': frozenset({'write_sandbox_note', 'export_sandbox_summary'}),
    'auditor': frozenset(),
}
ID_PATTERN = re.compile(r'^INC-\d{3}$')
LOCK = threading.RLock()

class PolicyDenied(Exception):
    pass


def _stable(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def issue_grant(secret: bytes, *, role: str, case_id: str, tool: str, ttl_seconds=300, now=None) -> str:
    """Issue short-lived scoped capability. Not meant to be given to an LLM."""
    if not isinstance(secret, bytes) or len(secret) < 32:
        raise ValueError('Secret must contain at least 32 random bytes')
    if (role not in ROLE_PERMISSIONS or tool not in SAFE_TOOLS or
            tool not in ROLE_PERMISSIONS[role] or not ID_PATTERN.fullmatch(case_id)):
        raise PolicyDenied('Grant scope is not permitted')
    if not isinstance(ttl_seconds, int) or not 1 <= ttl_seconds <= 900:
        raise ValueError('TTL must be 1..900 seconds')
    now = now or datetime.now(timezone.utc)
    payload = {'role': role, 'case_id': case_id, 'tool': tool,
               'expires_at': int((now + timedelta(seconds=ttl_seconds)).timestamp()),
               'nonce': secrets.token_hex(16), 'version': 1}
    from base64 import urlsafe_b64encode
    body = urlsafe_b64encode(_stable(payload).encode()).decode().rstrip('=')
    mac = hmac.new(secret, body.encode(), hashlib.sha256).hexdigest()
    return f'{body}.{mac}'


def _verify_grant(grant: str, secret: bytes, *, now=None) -> dict:
    from base64 import urlsafe_b64decode
    try:
        if not isinstance(grant, str) or len(grant) > 2048:
            raise ValueError('invalid length')
        body, received = grant.split('.')
        mac = hmac.new(secret, body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(mac, received):
            raise ValueError('signature mismatch')
        payload = json.loads(urlsafe_b64decode(body + '=' * (-len(body) % 4)))
        if set(payload) != {'role', 'case_id', 'tool', 'expires_at', 'nonce', 'version'}:
            raise ValueError('invalid scope')
        if payload['version'] != 1 or not isinstance(payload['expires_at'], int):
            raise ValueError('invalid version')
        if int((now or datetime.now(timezone.utc)).timestamp()) >= payload['expires_at']:
            raise ValueError('expired')
        return payload
    except (ValueError, TypeError, KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PolicyDenied('Invalid, expired, or forged grant') from exc


def _write_atomic(path: Path, content: str):
    """Write only to a preconstructed sandbox path; never accept a path from agent input."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + secrets.token_hex(6) + '.tmp')
    try:
        with temp.open('x', encoding='utf-8') as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def execute_sandbox_tool(output_dir: Path, *, role: str, case_id: str, tool: str,
                         note: str, grant: str, secret: bytes, now=None) -> dict:
    """Enforce role, scope, action, gate, audit integrity, and replay protection.

    Gate decisions are never overridden. Blocked cases cannot use even demo tools.
    No medical or external action tool exists. All effects are local text drafts.
    """
    output_dir = Path(output_dir)
    audit_path = output_dir / 'audit_log.jsonl'
    with LOCK:
        # Don't trust the requested actor, tool name, or untrusted free text.
        if (not audit_path.is_file() or not verify_chain(audit_path)):
            raise PolicyDenied('Audit integrity required')
        if tool not in SAFE_TOOLS or role not in ROLE_PERMISSIONS or tool not in ROLE_PERMISSIONS[role]:
            append_event(audit_path, {'event_type': 'tool_denied', 'case_id': str(case_id)[:80],
                                      'tool': str(tool)[:80], 'reason': 'tool_or_role_not_allowed'})
            raise PolicyDenied('Tool not permitted for this role')
        if not ID_PATTERN.fullmatch(case_id):
            raise PolicyDenied('Invalid incident ID')
        scoped = _verify_grant(grant, secret, now=now)
        if (scoped['role'], scoped['case_id'], scoped['tool']) != (role, case_id, tool):
            raise PolicyDenied('Grant does not match requested scope')
        if not isinstance(note, str) or not 10 <= len(note) <= 2000 or '\x00' in note:
            raise PolicyDenied('Invalid sandbox note')
        cases = load_cases(output_dir)
        match = [x for x in cases if x['incident'].get('id') == case_id]
        if len(match) != 1 or match[0]['gate'].get('decision') != 'ALLOW_ROUTINE_DRAFT':
            append_event(audit_path, {'event_type': 'tool_denied', 'case_id': case_id,
                                      'tool': tool, 'reason': 'gate_blocked_or_case_missing'})
            raise PolicyDenied('Authority Gate prohibits this action')
        # Track consumptions in the verified audit chain; prevents replay after restart.
        # This is still not a transactional or immutable enterprise ledger.
        for line in audit_path.read_text(encoding='utf-8').splitlines():
            event = json.loads(line)
            if event.get('event_type') == 'sandbox_tool_used' and event.get('nonce') == scoped['nonce']:
                raise PolicyDenied('Grant already consumed')
        # No path comes from the model or the caller; no shell, network, or clinical connector.
        folder = output_dir / 'sandbox_actions'
        target = folder / f'{case_id}_{tool}.txt'
        content = f'SYNTHETIC DEMO — NOT A CLINICAL RECORD\nIncident: {case_id}\nTool: {tool}\nDraft: {note}\n'
        # Audit event is written before the output. If output fails, audit remains evidence
        # of attempted execution; review status manually. This is not atomic across files.
        append_event(audit_path, {'event_type': 'sandbox_tool_used', 'case_id': case_id,
                                  'tool': tool, 'role': role, 'nonce': scoped['nonce'],
                                  'note_sha256': hashlib.sha256(note.encode()).hexdigest()})
        _write_atomic(target, content)
        return {'status': 'SANDBOX_DRAFT_WRITTEN', 'case_id': case_id, 'tool': tool,
                'path': str(target), 'clinical_execution': False}
