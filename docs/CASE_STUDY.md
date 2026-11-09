# CardioAhead-GovAgent v0.4 — AI Safety Engineering Case Study

**An authority-gated agent orchestration prototype for synthetic medical AI incident triage.**  
**Thesis:** *Capability does not grant authority.*  
**Status:** Local functional prototype; **37/37 automated tests passed**, 9 November 2026.

## Executive summary
CardioAhead-GovAgent separates an AI's ability to draft safety-analysis notes from its permission to execute actions. An optional LLM can extract a failure-mode summary and evidence gaps, but a deterministic Python **Authority Gate** uses separately provided synthetic case metadata to decide whether a routine draft is permitted or a case must be escalated. A second **Tool Boundary** enforces role permissions, scoped and time-limited HMAC grants, replay protection, case gate state and audit-chain verification before any synthetic file-write effect.

**This is not** a medical device, clinical decision support product, real CAPA platform, regulatory conformity assessment, OS-level sandbox, or validated AI safety system. No actual patient data, clinical system, or external action adapter is involved. A live LLM service has not been exercised in this environment.

## Architecture

```text
Synthetic incident
       |
Mock triage / optional LLM draft notes (untrusted)
       |
Illustrative regulatory mapping
       |
Deterministic Authority Gate (default deny)
       |                          |
Routine draft only          Block + human review
       |                          |
       +------------+-------------+
                    |
         Audit + local Dashboard
                    |
         Independent Tool Boundary
          (RBAC + scoped HMAC grant
          + case state + audit integrity)
                    |
        Local synthetic .txt draft ONLY
```

## Demonstrated results

| Incident | Synthetic description | Policy decision |
|---|---|---|
| INC-001 | Non-clinical UI display defect | `ALLOW_ROUTINE_DRAFT` |
| INC-002 | Sensor drift and delayed status notification | `ALLOW_ROUTINE_DRAFT` |
| INC-003 | False-negative arrhythmia detection; threshold modification | `BLOCK_AND_ESCALATE` |
| INC-004 | ECG pipeline schema change | `ALLOW_ROUTINE_DRAFT` |
| INC-005 | Unreliable ECG explanation; physician flag override | `BLOCK_AND_ESCALATE` |

The allowed sandbox adapters are `write_sandbox_note` and `export_sandbox_summary`. Both write only synthetic text drafts into a fixed `sandbox_actions` directory. **No clinical action tool exists.** Review acknowledgement does not override the block.

## Security test evidence

The repository's unittest suite was executed locally: **37 tests passed**. Negative tests include critical-case denial despite an otherwise valid grant, role denial, unimplemented clinical tool refusal, forged/expired/wrong-case/wrong-tool/replayed grants, path traversal, modified audit chain, prompt-like text handled as inert data, and read-only auditor blocked from review POST.

This is functional evidence for the implemented paths, **not proof of broad AI robustness or production security**.

## Threats and limitations

- **Trust boundary:** The model may submit only two commentary fields (`failure_mode_summary`, `evidence_gaps`). It does not decide permissions, software class, or clinical actions.
- **Trusted issuer:** HMAC grants assume an external trusted caller. There is no enterprise identity provider, external key service or verified clinician identity.
- **Audit:** Hash-linked local audit records are tamper-evident against simple edits, **not immutable**; a privileged local attacker could rewrite the chain and case report. Multi-file writes are not transactional.
- **Isolation:** The sandbox is a deliberately constrained local file writer, not container/OS confinement.
- **Human oversight:** The local password-protected reviewer/auditor dashboard is a workflow demonstration, not evidence of effective clinical oversight or reduced automation bias.
- **Regulatory scope:** ISO 14971, IEC 62304 and EU AI Act Articles 14 and 72 are contextual references, not compliance claims. IEC 62304 A/B/C values are illustrative, not generic low/medium/high risk ratings.
- **External service:** Live OpenAI-compatible API integration exists in code but was not end-to-end tested with a provider.

## Reproduce locally

Python 3.10+; mock mode uses standard-library Python only.

```bash
python main.py --mode mock --output output/v04_demo
python tool_demo.py --output output/v04_demo --case INC-001
python tool_demo.py --output output/v04_demo --case INC-003  # DENIED is expected
python -m unittest discover -s tests -v
python -m dashboard.app --output output/v04_demo --port 8765
```

Use a fresh output directory for separate demo runs; keep the dashboard bound to localhost. Do **not** put real patient data or credentials in the repository.

## Next engineering milestones

1. Version-pinned reproducible demonstration, annotated threat model, test-to-policy evidence matrix.
2. Protected/signed case state, stronger audit anchoring and crash-consistent persistence.
3. Container/process isolation, network limits and separate key management.
4. Human-factor studies measuring whether reviewers actually understand, challenge and override automation appropriately.

## Engineering takeaway

> A model's recommendation is not a permission token. Independent, testable enforcement must sit at the action boundary.

**Key code:** `governance/authority_gate.py`, `governance/tool_boundary.py`, `agents/llm_triage.py`, `dashboard/app.py`, `tests/test_v04.py`.
