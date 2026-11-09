"""Local demonstration review workflow. Never authorizes external or clinical execution."""
from __future__ import annotations
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from governance.audit import append_event, verify_chain

LOCK = threading.RLock()
ACTIONS = {"acknowledge", "reject", "request_changes"}

class ReviewError(Exception):
    pass


def load_cases(output_dir: Path):
    report = output_dir / "risk_report.json"
    if not report.is_file():
        raise ReviewError("Generate risk report using main.py before opening dashboard")
    data = json.loads(report.read_text(encoding="utf-8"))
    if not isinstance(data, list) or any(not isinstance(x, dict) or 'incident' not in x or 'gate' not in x for x in data):
        raise ReviewError("Invalid case report")
    return data


def load_reviews(output_dir: Path):
    path = output_dir / "reviews.json"
    if not path.exists():
        return {}
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ReviewError("Invalid review storage")
    return obj


def submit_review(output_dir: Path, case_id: str, action: str, reason: str, reviewer="local-reviewer"):
    if action not in ACTIONS:
        raise ReviewError("Invalid review action")
    reason = reason.strip()
    if not 10 <= len(reason) <= 1000:
        raise ReviewError("Review rationale must contain 10–1000 characters")
    if not reviewer or len(reviewer)>100:
        raise ReviewError("Invalid reviewer")
    with LOCK:
        log = output_dir / "audit_log.jsonl"
        if not log.exists() or not verify_chain(log):
            raise ReviewError("Audit record missing or failed integrity check; review disabled")
        cases = load_cases(output_dir)
        matches = [x for x in cases if x['incident'].get('id') == case_id]
        if len(matches) != 1:
            raise ReviewError("Case not found or ambiguous")
        case = matches[0]
        reviews = load_reviews(output_dir)
        if case_id in reviews:
            raise ReviewError("Already reviewed; updates require a new review cycle")
        # Review acknowledges a draft; it never changes the authority gate decision.
        # High-risk blocked cases may be acknowledged as reviewed but NEVER released.
        current = {
            "case_id": case_id, "review_status": action,
            "reviewer": reviewer, "rationale": reason,
            "reviewed_at_utc": datetime.now(timezone.utc).isoformat(),
            "gate_decision_unchanged": case['gate']['decision'],
            "execution_authorized": False,
        }
        # Audit first; a failed persistence must not appear successful to caller.
        append_event(log, {"event_type": "human_review", **current})
        reviews[case_id] = current
        target = output_dir / "reviews.json"
        tmp = output_dir / "reviews.json.tmp"
        try:
            with tmp.open('w', encoding='utf-8') as f:
                json.dump(reviews, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, target)
        finally:
            tmp.unlink(missing_ok=True)
        return current
