"""Run the repeatable local V6-V8 gates and write a small evidence report.

This deliberately exercises only local contracts and test fixtures. Real model,
test/staging host, and enterprise tenant checks remain manual acceptance steps.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Sequence


ROOT = Path(__file__).resolve().parents[2]
OPS_ADMIN = ROOT / "ops-admin"
OPENSRE = ROOT / "opensre"
EVIDENCE = ROOT / ".todo" / "sre-platform-v2" / "evidence"


def run_gate(name: str, cwd: Path, command: Sequence[str]) -> dict[str, object]:
    started = dt.datetime.now(dt.timezone.utc)
    try:
        completed = subprocess.run(
            list(command), cwd=cwd, text=True, capture_output=True, check=False,
            env=os.environ.copy(),
        )
    except OSError as exc:
        return {"name": name, "status": "failed", "command": list(command), "output": str(exc)}
    output = (completed.stdout + "\n" + completed.stderr).strip()
    # Keep the report useful without copying long model or connector output.
    tail = "\n".join(output.splitlines()[-24:])
    return {
        "name": name,
        "status": "passed" if completed.returncode == 0 else "failed",
        "command": list(command),
        "exit_code": completed.returncode,
        "duration_seconds": round((dt.datetime.now(dt.timezone.utc) - started).total_seconds(), 2),
        "output_tail": tail,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-web-regression", action="store_true", help="skip node browser regression tests")
    parser.add_argument("--skip-compose", action="store_true", help="skip Docker Compose syntax validation")
    args = parser.parse_args()

    gates: list[dict[str, object]] = [
        run_gate(
            "ops-admin governance and connector tests",
            OPS_ADMIN / "backend",
            ["go", "test", "./service", "./controller", "./router", "./middleware",
             "-run", "Test(Action|Proposal|Enterprise|Feishu|NativeFeishu|MCP|Governance|Connector|AgentProfile)", "-count=1"],
        ),
        run_gate(
            "opensre readonly and mcp tests",
            OPENSRE,
            ["uv", "run", "--no-sync", "pytest", "-q", "integrations/ops_admin/tests",
             "gateway/tests/prompt_intake/test_readonly_profile.py", "gateway/tests/web/test_ops_admin_mcp.py"],
        ),
        run_gate("ops-admin web production build", OPS_ADMIN / "web", ["npm", "run", "build"]),
        run_gate(
            "fixture syntax",
            OPS_ADMIN / "web",
            ["node", "--check", "tests/fixtures/ai-investigation-server.mjs"],
        ),
        run_gate(
            "revocation fixture syntax",
            OPS_ADMIN / "web",
            ["node", "--check", "tests/fixtures/ai-investigation-revocation.mjs"],
        ),
    ]
    if not args.skip_web_regression:
        gates.append(run_gate("ops-admin web regression", OPS_ADMIN / "web", ["npm", "run", "test:regression"]))

    compose_file = OPS_ADMIN / "docker-compose.investigations.yml"
    compose_env = OPS_ADMIN / "deploy" / "opensre.local.env"
    if not args.skip_compose and shutil.which("docker") and compose_env.exists():
        env = os.environ.copy()
        env.update({
            "INVESTIGATION_SERVICE_TOKEN": "local-v6-v8-service-token",
            "INVESTIGATION_QUERY_KEY": "local-v6-v8-query-key-012345678901234567890123456789",
            "OPS_ADMIN_OPENSRE_SERVICE_TOKEN": "local-v6-v8-mcp-token",
        })
        original = os.environ.copy()
        os.environ.update(env)
        gates.append(run_gate("investigation compose syntax", OPS_ADMIN, ["docker", "compose", "-f", str(compose_file), "config", "--quiet"]))
        os.environ.clear()
        os.environ.update(original)
    else:
        gates.append({
            "name": "investigation compose syntax",
            "status": "skipped",
            "reason": "docker or deploy/opensre.local.env is unavailable; copy the example before local compose validation",
        })

    EVIDENCE.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    report = EVIDENCE / f"v6-v8-local-{stamp}.md"
    lines = ["# V6–V8 本地验收证据", "", f"生成时间：{dt.datetime.now().astimezone().isoformat()}", ""]
    lines.append("本报告只记录本地代码、契约和隔离测试；真实模型、测试/预发主机、原生企业平台和租户仍需人工验收。")
    lines.append("")
    for gate in gates:
        lines.append(f"## {gate['name']}")
        lines.append(f"- 状态：`{gate['status']}`")
        if gate.get("command"):
            lines.append(f"- 命令：`{' '.join(str(item) for item in gate['command'])}`")
        if gate.get("reason"):
            lines.append(f"- 原因：{gate['reason']}")
        if gate.get("exit_code") is not None:
            lines.append(f"- 退出码：`{gate['exit_code']}`，耗时 `{gate.get('duration_seconds', 0)}s`")
        if gate.get("output_tail"):
            lines.extend(["", "```text", str(gate["output_tail"]), "```"])
        lines.append("")
    report.write_text("\n".join(lines), encoding="utf-8")
    failed = [gate for gate in gates if gate["status"] == "failed"]
    print({"status": "failed" if failed else "passed", "report": str(report), "gates": gates})
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
