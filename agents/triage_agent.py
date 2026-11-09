"""Deterministic mock triage; intentionally no clinical inference."""

def triage(incident: dict) -> dict:
    required = ["id", "description", "illustrative_severity", "illustrative_iec62304_class", "proposed_action", "uncertainty", "evidence_note"]
    missing = [name for name in required if name not in incident]
    if missing:
        raise ValueError(f"Missing fields: {missing}")
    if not isinstance(incident["uncertainty"], (int, float)) or not 0 <= incident["uncertainty"] <= 1:
        raise ValueError("uncertainty must be in [0, 1]")
    return {**incident, "failure_mode": incident["description"], "triage_status": "draft_not_validated"}
