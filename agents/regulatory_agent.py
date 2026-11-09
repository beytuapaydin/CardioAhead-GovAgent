"""Educational mapping. NOT a real regulatory classification engine."""

def regulatory_map(item: dict) -> dict:
    return {**item, "regulatory_notes": {
        "ISO_14971": "Evaluate hazards, hazardous situations, possible harms and risk controls; no automated compliance decision.",
        "IEC_62304": "Illustrative software safety class is provided as input, not inferred from severity or likelihood. Verify classification through documented safety analysis.",
        "EU_AI_Act_Art_14": "Consider effective human oversight and automation bias if the applicable high-risk AI obligations apply.",
        "EU_AI_Act_Art_72": "Consider post-market monitoring requirements and applicable medical device sector-law coordination; applicability needs legal review."
    }, "capa_draft": "Human review required before CAPA creation or technical-file approval.",
    "compliance_status": "NOT_ASSESSED"}
