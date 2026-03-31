"""Quality gate tools — Jidoka + Poka-Yoke as MCP tools.

These can be registered with the Claude Agent SDK so agents
can invoke quality checks as tool calls.
"""

from __future__ import annotations

import subprocess
from typing import Any

from claude_agent_sdk import tool


@tool(
    "run_quality_gates",
    "Run all quality gates (ruff format, ruff check, pytest) and report results",
    {"project_dir": str},
)
async def run_quality_gates(args: dict[str, Any]) -> dict[str, Any]:
    """Poka-Yoke: automated mistake prevention."""
    project_dir = args["project_dir"]
    results: dict[str, Any] = {}
    all_passed = True

    gates = [
        ("format", ["ruff", "format", "--check", "."]),
        ("lint", ["ruff", "check", "."]),
        ("test", ["pytest", "--tb=short", "-q"]),
    ]

    for name, cmd in gates:
        try:
            result = subprocess.run(
                cmd,
                cwd=project_dir,
                capture_output=True,
                text=True,
                timeout=120,
            )
            passed = result.returncode == 0
            results[name] = {
                "passed": passed,
                "output": result.stdout[-500:] if result.stdout else "",
                "errors": result.stderr[-500:] if result.stderr else "",
            }
            if not passed:
                all_passed = False
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            results[name] = {"passed": False, "output": "", "errors": str(e)}
            all_passed = False

    summary = "ALL GATES PASSED" if all_passed else "SOME GATES FAILED"
    detail = "\n".join(
        f"  {k}: {'PASS' if v['passed'] else 'FAIL'}" for k, v in results.items()
    )

    return {
        "content": [{"type": "text", "text": f"{summary}\n{detail}"}],
        "isError": not all_passed,
    }


@tool(
    "jidoka_check",
    "Check if any critical issues warrant stopping the line",
    {"defects_json": str},
)
async def jidoka_check(args: dict[str, Any]) -> dict[str, Any]:
    """Jidoka: determine if we need to stop the line."""
    import json

    try:
        defects = json.loads(args["defects_json"])
    except json.JSONDecodeError:
        return {"content": [{"type": "text", "text": "Could not parse defects JSON"}]}

    critical = [d for d in defects if d.get("severity") == "critical"]
    high = [d for d in defects if d.get("severity") == "high"]

    if critical:
        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"JIDOKA: STOP THE LINE\n"
                        f"{len(critical)} critical defect(s) found.\n"
                        f"All work must stop until resolved."
                    ),
                }
            ],
            "isError": True,
        }

    if high:
        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"WARNING: {len(high)} high-severity defect(s).\n"
                        f"Related work should pause for investigation."
                    ),
                }
            ],
        }

    return {
        "content": [{"type": "text", "text": "No critical defects. Continue."}]
    }
