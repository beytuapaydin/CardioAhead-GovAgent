"""Independent, deterministic policy enforcement. Default deny for unknown actions."""
from governance.audit import append_event

HIGH_RISK_ACTIONS = {"modify_clinical_threshold", "override_physician_flag"}
ROUTINE_ACTIONS = {"document_only", "create_capa_draft", "update_documentation"}

def evaluate(item: dict, audit_path) -> dict:
    action = item.get("proposed_action")
    cls = item.get("illustrative_iec62304_class")
    reasons = []
    if cls not in {"A", "B", "C"}: reasons.append("invalid_or_unknown_software_safety_class")
    if action not in HIGH_RISK_ACTIONS | ROUTINE_ACTIONS: reasons.append("unknown_action_default_deny")
    if cls == "C": reasons.append("illustrative_class_C_requires_review")
    if item.get("triage_status") == "llm_failed_needs_review": reasons.append("llm_failure_default_deny")
    if action in HIGH_RISK_ACTIONS: reasons.append("safety_critical_action_not_autonomous")
    if item.get("uncertainty", 1) > 0.7: reasons.append("high_uncertainty_requires_review")
    blocked = bool(reasons)
    result = {"incident_id": item["id"], "requested_action": action, "decision": "BLOCK_AND_ESCALATE" if blocked else "ALLOW_ROUTINE_DRAFT", "reasons": reasons, "human_review_required": blocked, "executed": False, "source_evidence": item.get("evidence_note", "unknown"), "uncertainty": item.get("uncertainty", None), "review_notice": "Check counter-evidence, subgroup performance and alternatives before approval. No clinical or regulatory execution is available."}
    append_event(audit_path, result)
    return result
