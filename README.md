# CardioAhead-GovAgent

**Authority-gated AI agent orchestration for a synthetic medical-software risk workflow.**  
**Version:** v0.4 · **Stack:** Python 3.10+ (standard library) · **Status:** research/portfolio prototype

> **Capability does not grant authority.** An AI can suggest or describe an action; it cannot authorize itself to execute it.

## Why this project?

AI-generated risk assessments can be useful, but a persuasive recommendation is not an authorization decision. This prototype explores a practical engineering question: **Can independent controls prevent agent outputs from turning into unauthorized actions, even when a human reviews the case?**

The system processes five **fictional SaMD incidents**. A mock triage agent—or an optional live LLM endpoint—produces draft notes; a regulatory mapper adds illustrative context; a **deterministic Authority Gate** marks a case as routine or blocked. At the actual local file-write boundary, a second set of controls checks the case decision, role, scoped HMAC grant, expiry, replay status and audit integrity.

**No clinical action tool exists. No real patient, medical-device or regulatory system is connected.**

## Evidence at a glance

| Question | Demonstrated behavior |
|---|---|
| Can the LLM grant itself permission? | **No.** Model output is restricted to commentary fields and cannot modify permission-critical metadata. |
| Can a blocked incident act anyway? | **No in the tested demo paths.** Even a valid sandbox grant cannot bypass the case gate. |
| Can a reviewer approve clinical execution? | **No.** Human review records a disposition; it does not turn a blocked case into an executable one. |
| Can an unauthorized role or forged token write a note? | **Denied** by the tool boundary in the tested scenarios. |
| How is this verified? | **37 local automated tests passed**; [GitHub Actions](../../actions) also executes the suite on Python 3.10 and 3.12. |

**Read the engineering evidence:** [AI Safety Engineering Case Study](docs/CASE_STUDY.md) · [4-page PDF](docs/CardioAhead_GovAgent_v04_AI_Safety_Engineering_Case_Study.pdf) · [Security tests](tests/test_v04.py) · [CI workflow](.github/workflows/tests.yml).

## Architecture

```text
  Fictional incident + trusted illustrative metadata
                         |
            Mock triage / optional LLM
             (untrusted draft notes only)
                         |
             Illustrative regulatory map
                         |
               DETERMINISTIC AUTHORITY GATE
                   /                 \
         Routine draft          BLOCK + ESCALATE
                   \                 /
              Report + audit + local review UI
                         |
            INDEPENDENT TOOL BOUNDARY
       RBAC · scoped/expiring HMAC grant · no-replay
            case-state + audit-chain checks
                         |
           Allowlisted local .txt drafts ONLY
           (no external/clinical execution)
```

The reviewer dashboard supports **reviewer** and read-only **auditor** demonstration roles. The standalone sandbox-tool demo uses separately scoped roles and grants; these are **not** a shared enterprise identity system.

## Reproduce the demonstration

Python **3.10+** is required. Mock mode has no external dependencies or API costs.

```bash
python main.py --mode mock --output output/v04_demo
python -m unittest discover -s tests -v
python tool_demo.py --output output/v04_demo --case INC-001
python tool_demo.py --output output/v04_demo --case INC-003
```

**Expected outcome:** 37 tests pass; `INC-001` can write a synthetic note under a demo grant; `INC-003` is **DENIED** (exit status 2, expected) because a proposed clinical threshold change is blocked.

The five example incidents produce **three routine documentation drafts** (`INC-001`, `INC-002`, `INC-004`) and **two block-and-escalate outcomes** (`INC-003`, `INC-005`). These are illustrative classifications, not validated clinical risk decisions.

### Run the local Human Review Dashboard

First run the main workflow, then:

```bash
python -m dashboard.app --output output/v04_demo --port 8765
```

Open **http://127.0.0.1:8765** on the same computer. A temporary demo password is printed in the terminal if none is configured. For separate reviewer/auditor roles, set distinct strong `GOVAGENT_REVIEW_PASSWORD` and `GOVAGENT_AUDITOR_PASSWORD` environment variables before launching; see the code for supported settings.

**Local demo only:** do not expose this HTTP server to the public internet or through a tunnel. Use a **fresh output directory** for each new demonstration cycle; do not overwrite a run after recording reviews.

### Optional live LLM-assisted extraction

The code can call an OpenAI-compatible HTTPS chat-completions endpoint using `GOVAGENT_LLM_API_KEY`, `GOVAGENT_LLM_MODEL` and `GOVAGENT_LLM_ENDPOINT`. Example environment variable names are in [`.env.example`](.env.example); the application reads environment variables, not the example file.

```powershell
$env:GOVAGENT_LLM_API_KEY="YOUR_API_KEY"
$env:GOVAGENT_LLM_MODEL="YOUR_MODEL_NAME"
$env:GOVAGENT_LLM_ENDPOINT="https://api.openai.com/v1/chat/completions"
python main.py --mode llm --output output/llm
```

**Not live-tested with a provider in the documented evaluation.** Provider compatibility, reliability, costs and model behavior are unverified. Provider errors **block and escalate**, rather than silently falling back to the mock mode. **Never upload patient data or commit credentials.**

## Key implementation files

| Path | Responsibility |
|---|---|
| [`agents/llm_triage.py`](agents/llm_triage.py) | Restricted optional LLM note extraction |
| [`agents/regulatory_agent.py`](agents/regulatory_agent.py) | Illustrative regulatory mapping |
| [`governance/authority_gate.py`](governance/authority_gate.py) | Deterministic, default-deny incident policy |
| [`governance/tool_boundary.py`](governance/tool_boundary.py) | Scoped grants, role checks and sandbox action enforcement |
| [`governance/audit.py`](governance/audit.py) | Hash-linked local audit verification |
| [`dashboard/app.py`](dashboard/app.py) | Local human review and read-only auditor UI |
| [`tests/test_v04.py`](tests/test_v04.py) | Negative / boundary tests |
| [`data/synthetic_incidents.json`](data/synthetic_incidents.json) | Five fictional incidents |

## Security and regulatory boundaries

- **Not for patient care.** This is not a medical device, real CAPA/post-market monitoring system, validated clinical-risk assessment, conformity assessment, or legal advice.
- **Standards are context, not certification.** ISO 14971, IEC 62304 and EU AI Act Articles 14/72 inform the discussion; their complete requirements are **not** implemented or verified. IEC 62304 A/B/C labels are software safety classes, not generic low/medium/high risk scores; values in these fixtures are illustrative.
- **No real safety sandbox.** Only a fixed local synthetic text-file adapter is implemented—not OS/container isolation, shell-access safety, production network restrictions or secure enterprise identity.
- **Human review is not execution authority.** A dashboard acknowledgement cannot override a blocked case; local password/role controls do not establish qualified clinical oversight or solve automation bias.
- **Audit is tamper-evident, not immutable.** A local attacker with broad filesystem access may rewrite records and the hash chain. There is no external anchoring, protected state store, or transactional multi-file persistence.
- **Testing has a defined scope.** The automated tests exercise implemented policies and simulated attacks; they do **not** prove robustness against arbitrary prompt injection, a compromised host, a malicious trusted grant issuer, or real autonomous systems.

For the full threat model, attack cases, design assumptions and next steps, see the [case study](docs/CASE_STUDY.md).

## Development transparency

This portfolio prototype was **implemented largely with AI coding assistance**, including significant contributions to architecture, code, tests and documentation. The repository owner initiated the project direction and is working through the system's implementation, verification and engineering decisions to develop independent technical ownership. The repository is presented as an **AI-assisted engineering learning and evaluation artifact**, not evidence of independently implementing or validating a production medical AI system.

## Next engineering questions

1. Can a protected workflow-state store and independent audit anchoring prevent a privileged local process from rewriting case decisions?
2. How should trusted authorization issuers and human reviewers be authenticated independently of agents?
3. Can controlled live-model trials measure rule violations and evidence quality beyond mocked responses?
4. What human-factors tests distinguish meaningful oversight from automation-bias-driven rubber-stamping?
