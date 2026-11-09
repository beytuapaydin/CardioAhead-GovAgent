"""Governed simulation. --mode llm adds extraction; authorization stays deterministic."""
import argparse
import json
import os
from pathlib import Path
from agents.triage_agent import triage
from agents.llm_triage import llm_triage, TriageProviderError
from agents.regulatory_agent import regulatory_map
from governance.authority_gate import evaluate
from governance.audit import verify_chain

ROOT = Path(__file__).resolve().parent


def run(output_dir: Path, *, mode: str = "mock", endpoint: str | None = None,
        model: str | None = None, api_key: str | None = None):
    if mode not in {"mock", "llm"}:
        raise ValueError("mode must be 'mock' or 'llm'")
    if mode == "llm" and (not endpoint or not model or not api_key):
        raise ValueError("LLM mode requires endpoint, model, API key")
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / "audit_log.jsonl"
    if log_path.exists() and not verify_chain(log_path):
        raise RuntimeError("Existing audit chain invalid; refusing to continue")
    incidents = json.loads((ROOT / "data/synthetic_incidents.json").read_text(encoding="utf-8"))
    results = []
    for incident in incidents:
        try:
            draft = (llm_triage(incident, endpoint=endpoint, model=model, api_key=api_key)
                     if mode == "llm" else triage(incident))
        except TriageProviderError as exc:
            # A provider failure must not silently become an approved routine action.
            draft = {**triage(incident), "triage_status": "llm_failed_needs_review", "llm_error": str(exc)}
        reviewed = regulatory_map(draft)
        decision = evaluate(reviewed, log_path)
        results.append({"incident": reviewed, "gate": decision})
        print(f"{incident['id']}: {decision['decision']} — {', '.join(decision['reasons']) or 'routine draft only'}")
    (output_dir / "risk_report.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    (output_dir / "human_review_queue.json").write_text(json.dumps([r for r in results if r['gate']['human_review_required']], indent=2), encoding="utf-8")
    print(f"Audit chain valid: {verify_chain(log_path)}")
    print(f"Outputs: {output_dir}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "output")
    parser.add_argument("--mode", choices=("mock", "llm"), default="mock")
    parser.add_argument("--endpoint", default=os.environ.get("GOVAGENT_LLM_ENDPOINT", "https://api.openai.com/v1/chat/completions"))
    parser.add_argument("--model", default=os.environ.get("GOVAGENT_LLM_MODEL"))
    args = parser.parse_args()
    run(args.output, mode=args.mode, endpoint=args.endpoint, model=args.model, api_key=os.environ.get("GOVAGENT_LLM_API_KEY"))
