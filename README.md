# CardioAhead-GovAgent v0.4

**Governed agent-orchestration demonstration for fictional SaMD incident triage.**

> **Capability does not grant authority.** The optional LLM extracts *draft notes*, while an independent deterministic Python gate decides whether an item can proceed to routine documentation or must enter human review. No clinical, regulatory, or external system changes are ever executed.

## Architecture

```text
Synthetic incidents (trusted illustrative incident metadata + untrusted text)
                 |
          Triage Agent (mock OR optional LLM-assisted draft extraction)
                 |               [LLM output: summary + evidence gaps ONLY]
                 v
         Regulatory Mapping (illustrative references, not legal decisions)
                 |
                 v
         DETERMINISTIC AUTHORITY GATE (never asks the LLM for permission)
              /                                      \
      Routine draft only                       BLOCK + Review Queue
              \                                      /
               v                                    v
            Risk report + hash-linked, tamper-evident local audit log
```

## Quick start (Python 3.10+, standard library only)

From the extracted project folder:

```bash
python main.py --mode mock --output output/mock
python -m unittest discover -s tests -v
```

The expected results are **INC-001, 002, 004** as routine *drafts*, and **INC-003, 005** as `BLOCK_AND_ESCALATE`. No side-effecting tools or medical systems are used.

## Optional: real LLM-assisted extraction

Requires your own access to an **OpenAI-compatible HTTPS chat-completions endpoint**, valid model identifier, credentials, and network access. The live API call has **not been exercised in this environment**. Provider compatibility can vary (some providers do not accept `temperature` or the same response format).

**Windows PowerShell:**

```powershell
$env:GOVAGENT_LLM_API_KEY="YOUR_API_KEY"
$env:GOVAGENT_LLM_MODEL="YOUR_MODEL_NAME"
$env:GOVAGENT_LLM_ENDPOINT="https://api.openai.com/v1/chat/completions"
python main.py --mode llm --output output/llm
```

**Linux/macOS:**

```bash
export GOVAGENT_LLM_API_KEY="YOUR_API_KEY"
export GOVAGENT_LLM_MODEL="YOUR_MODEL_NAME"
export GOVAGENT_LLM_ENDPOINT="https://api.openai.com/v1/chat/completions"
python main.py --mode llm --output output/llm
```

Replace placeholder values with a model and endpoint you have access to. Credentials are read from environment variables, not written to the report. Do not commit credentials to Git. **Only use the included synthetic demo inputs** with third-party services. Provider requests may incur charges.

If a provider fails, the system **blocks and escalates** instead of silently approving or switching to mock. The model is asked to return only `failure_mode_summary` and `evidence_gaps`; any attempt to add permission, risk class, or action fields is rejected. Trusted incident metadata is never updated from the LLM answer. This is a demonstration of a restricted model-data boundary, not a comprehensive prompt injection defense.

## Folder layout

```text
agents/triage_agent.py       Deterministic baseline
agents/llm_triage.py         Optional real model request with strict output schema
agents/regulatory_agent.py   Illustrative regulatory mapping
 governance/authority_gate.py  Independent default-deny policy
 governance/audit.py          Hash-linked append-only local log with verification
 data/synthetic_incidents.json  Five fictional cases
 tests/test_project.py        Unit and simulated integration tests
 tests/test_dashboard.py      Dashboard and review security tests
 dashboard/app.py             Local reviewer HTTP UI
 governance/review.py         Review action validation and persistence
 main.py                      Entry point
```

## Security and regulatory limitations

- **Not a medical device, not for patient care, not a CAPA system, not a conformity assessment, and not legal advice.** No real patient data should be submitted. Model output is unverified and should not be treated as facts.
- **IEC 62304 classes A/B/C are not generic low/medium/high risk scores.** The synthetic labels are illustrative caller-supplied inputs; true classification requires documented hazard and risk analysis. Real world risk acceptance cannot rely on this simplified gate.
- **EU AI Act Article 14 / Article 72 and ISO 14971 are references, not certificates of compliance.** Determining applicability and satisfying their complete obligations require further assessment.
- **`ALLOW_ROUTINE_DRAFT` is not execution approval**: all decisions include `executed: false`. No live tool capable of editing patient data, clinical thresholds, regulatory records, or permissions is connected.
- **Audit is tamper-evident, not immutable.** An adversary with local filesystem access can re-create the hash chain. Production needs authenticated independent audit storage, protected anchoring, access control and lifecycle management. Do not erase audit files between runs; use separate output directories for fresh test runs.
- **The review UI is authenticated locally**, but not an authenticated *clinician* or enterprise review system. Meaningful human oversight needs qualified reviewers, evidence, counter-evidence, separation of duties, and control of automation bias.
- **Real agent safety is not proven.** No adversarial red team or production integration has been carried out. Provider calls have not been live-tested; local tests use mocked network responses.

## v0.3 — Local human review dashboard

**This version adds an actual browser dashboard with a password-protected local reviewer login.** It is a local single-reviewer demonstration, **not** an enterprise IAM solution. The dashboard exposes NO clinical action-execution endpoint. An `acknowledge` click only records that a person reviewed a case: the original `BLOCK_AND_ESCALATE` authority decision remains unchanged.

From the project directory, with Python 3.10+:

```bash
python main.py --mode mock --output output/demo
python -m dashboard.app --output output/demo --port 8765
```

Open **http://127.0.0.1:8765** on the same computer. If no password is configured, a temporary password will be printed in the terminal. You can instead set a password of 12+ characters before starting:

Windows PowerShell:

```powershell
$env:GOVAGENT_REVIEW_PASSWORD="YOUR_LONG_RANDOM_PASSWORD"
python -m dashboard.app --output output/demo
```

Linux/macOS:

```bash
export GOVAGENT_REVIEW_PASSWORD="YOUR_LONG_RANDOM_PASSWORD"
python -m dashboard.app --output output/demo
```

The page shows five synthetic incidents, their gate decisions and evidence, and offers three review dispositions: **Acknowledge review only**, **Request changes**, **Reject**. Reviewers must enter a rationale. Each case can be reviewed once in the current demo run, and every review is appended to the hash-linked audit trail. Results are also written to `reviews.json` in the chosen output directory.

The review UI only listens on `127.0.0.1`, uses a local password, HttpOnly/SameSite session cookies, anti-CSRF tokens, HTML escaping, and no third-party frontend dependencies. **Do not expose this local HTTP service to the internet**, including through tunnel services or reverse proxies. It does not provide TLS, multi-user identity, durable sessions, role-based enterprise access, hardened rate limits, audit anchoring, or workflow approval signatures. Its `reviewer` identity is a demo label, not independently verified proof of the human's identity.

**Test all versions:**

```bash
python -m unittest discover -s tests -v
```

**Limitations important for demo credibility**:

- No action execution is available anywhere in v0.3. Acknowledging a blocked case *never* overrides the gate.
- Hash chaining is **tamper-evident only against simple edits**, not against a filesystem attacker able to rewrite the entire chain. There is no immutable external audit anchoring.
- Incidents and their IEC 62304 classes are illustrative trusted fixtures. The application cannot classify real medical software or perform clinical risk acceptance.
- The dashboard is intentionally local and single-reviewer; deployable production access control would require a redesigned auth/authorization and hosting architecture.
- The dashboard consumes a previously generated report. Do not rerun `main.py` into the same output folder after reviews: use a fresh output folder per demonstration cycle.
- This prototype does not provide a validated post-market surveillance process, automated CAPA workflow, or EU AI Act Article 14/72 conformance.

## Original v0.4 roadmap (implemented in the section below)

Add a sandbox-only action adapter with **enforcement at the tool boundary**, explicit approval scope and expiry, signed external audit anchoring, and formal multi-user RBAC. No patient-care integrations are planned.

## References

- EU AI Act Article 14: https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-14
- EU AI Act Article 72: https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-72

---

## v0.4 — Independent tool-boundary enforcement and role separation

The application now includes `governance/tool_boundary.py`, `tool_demo.py`, and
`tests/test_v04.py`. **All v0.3 functions remain available.** The standalone
sandbox action demo adds a *separate* enforcement check at the side-effect
boundary. The model cannot grant itself credentials or use arbitrary tools.

### Three-step enforcement architecture

```text
1. AI (mock or optional LLM) produces draft notes
        |
2. Deterministic Authority Gate marks cases routine or blocked
        |
3. Sandbox Tool Boundary checks RBAC + scoped expiring HMAC grant
   + verified audit hash chain + no-replay + current case gate decision
        |
       only safe local synthetic text drafts (NO clinical execution)
```

**Allowlisted sandbox tools**: `write_sandbox_note` and
`export_sandbox_summary`. Both write only `.txt` drafts under the fixed
`output/<run>/sandbox_actions/` directory. `modify_clinical_threshold`,
`override_physician_flag`, shell execution, patient record modifications,
and permission changes have **no implementation**. Blocked incidents cannot
invoke *even* the safe sandbox tools.

**Role matrix**:

| Role | Read Dashboard | Submit human review | Sandbox note | Sandbox summary |
|---|---|---|---|---|
| reviewer | Yes | Yes | Yes, via scoped demo grant | No |
| auditor | Yes | No | No | No |
| operator | Not a Dashboard login role | No | Yes, via scoped demo grant | Yes, via scoped demo grant |
| viewer | Not a Dashboard login role | No | No | No |

The Dashboard login role and standalone tool simulation role are **separate
local demonstrations**, not shared IAM or cryptographically proven identities.
A `role` argument by itself does not constitute verified identity: in the
tool-boundary demo, a trusted caller obtains an HMAC-signed short-lived grant
outside the LLM. Never issue grants directly from an untrusted AI response.

### Quick test (no LLM, no dependencies beyond Python 3.10+)

```bash
python main.py --mode mock --output output/v04_demo
python tool_demo.py --output output/v04_demo --case INC-001
python tool_demo.py --output output/v04_demo --case INC-003
python -m unittest discover -s tests -v
```

The first tool demo writes `output/v04_demo/sandbox_actions/INC-001_write_sandbox_note.txt`.
The next is expected to print **DENIED** and return exit status **2** because
INC-003 is blocked. This expected denial is not a program defect.

To launch the updated dashboard with **separate reviewer and auditor** roles:

```powershell
$env:GOVAGENT_REVIEW_PASSWORD="LONG_DIFFERENT_REVIEW_PASSWORD"
$env:GOVAGENT_AUDITOR_PASSWORD="LONG_DIFFERENT_AUDITOR_PASSWORD"
python -m dashboard.app --output output/v04_demo --port 8765
```

Open `http://127.0.0.1:8765`; log in with reviewer or auditor credentials.
The auditor sees the incidents but cannot submit reviews. The reviewer may
record one reasoned disposition per case; blocked actions still cannot execute.
If no auditor password is configured, the legacy single-reviewer login is
preserved. Do not publish these demo credentials or expose this HTTP server.

### Adversarial evaluation

`tests/test_v04.py` covers, among others:

- A permitted synthetic note write under a scoped grant.
- A **Class C** clinical incident blocked despite a valid sandbox grant.
- A request for an unavailable clinical action rejected, including operator.
- Viewer/reviewer/operator role distinctions.
- Forged, expired, cross-case, cross-tool, and replayed grants denied.
- Untrusted input that resembles prompt injection stored as inert text only.
- Incident path traversal rejected by strict identifier validation.
- Audit-chain tampering preventing new actions.
- Read-only Dashboard auditor denied HTTP POST reviews.

### Important limitations and threat model

- This is a **local functional sandbox**, **not an OS/container security
  sandbox**. Real isolation requires process/container confinement, filesystem
  permissions, network restrictions, and resource controls.
- HMAC grants are scoped, signed and expire, but the **caller granting them is
  trusted by assumption**. There is no corporate SSO, durable multi-user IAM,
  or independently verified reviewer identity. Token secrets stay outside the
  model; leaked secrets allow forged tokens.
- Audit entries are local and hash-linked, **not immutable**. An attacker with
  unrestricted filesystem access can replace both the audit chain and reports.
  State persistence across several files is not transactional; a crash can
  leave an event recording an attempted write without the corresponding file.
- Report metadata is trusted demo input. A malicious process that can rewrite
  `risk_report.json` or local output files can undermine the policy. Production
  deployments need protected, signed, centrally validated workflow state.
- A prompt-injection-looking string is handled as inert data because the
  simulator does not evaluate or execute strings; this does **not** demonstrate
  broad prompt-injection resistance in an autonomous tool-using model.
- The standalone tool demo creates a new ephemeral HMAC secret per invocation;
  it models the grant flow but does not implement an enterprise approval
  service or persistent key management.
- Neither EU AI Act conformity nor ISO 14971/IEC 62304 compliance is implied.
  IEC 62304 class labels and rule thresholds are illustrative fixtures, not
  professional regulatory classifications.
- Continue using **synthetic incidents only**, not patient information.

**What v0.4 demonstrates:** the AI's ability to propose or describe an action
cannot authorize it at the tool boundary. **What v0.4 does not demonstrate:**
production-grade medical AI compliance, secure enterprise deployment, or a
validated clinical risk management workflow.
