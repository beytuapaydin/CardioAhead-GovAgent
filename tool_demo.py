"""Local sandbox demonstration. Generates a scoped grant outside of any LLM."""
import argparse
import secrets
from pathlib import Path
from governance.tool_boundary import issue_grant, execute_sandbox_tool, PolicyDenied

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Sandbox-only action simulation; no clinical execution')
    parser.add_argument('--output', type=Path, default=Path('output/demo'))
    parser.add_argument('--case', default='INC-001')
    parser.add_argument('--role', choices=['viewer','reviewer','operator','auditor'], default='operator')
    parser.add_argument('--tool', default='write_sandbox_note')
    parser.add_argument('--note', default='Illustrative investigation note for a synthetic incident.')
    a = parser.parse_args()
    secret = secrets.token_bytes(32)
    try:
        token = issue_grant(secret, role=a.role, case_id=a.case, tool=a.tool)
        outcome = execute_sandbox_tool(a.output, role=a.role, case_id=a.case,
                        tool=a.tool, note=a.note, grant=token, secret=secret)
        print(outcome)
    except PolicyDenied as exc:
        print(f'DENIED: {exc}')
        raise SystemExit(2)
