"""MCP Server for Lean Tech Agents.

Exposes task management, quality checks, and progress tracking
as an MCP server using FastMCP. Supports both stdio and HTTP transports.

One-liner for any user:
    uvx lean-tech-agents serve              # HTTP on port 8000
    uvx lean-tech-agents serve --stdio      # stdio for Claude Desktop JSON config

Or add as a remote connector in Claude Desktop:
    URL: http://localhost:8000/mcp
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from mcp.server.fastmcp import FastMCP

from lean_agents.config import settings
from lean_agents.lean.kanban import KanbanBoard
from lean_agents.lean.piscar import PiscarAnalysis
from lean_agents.models import Task, TaskStatus

# ---------------------------------------------------------------------------
# Global state (lives for the MCP session)
# ---------------------------------------------------------------------------

_kanban = KanbanBoard()

# ---------------------------------------------------------------------------
# FastMCP Server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "lean-tech-agents",
    instructions=(
        "Lean Tech Agents — agentic task management with built-in quality. "
        "Use plan_task first, then next_step/mark_done to work through steps. "
        "Flag problems with flag_problem, check quality with check_quality, "
        "and log lessons with log_lesson."
    ),
    host="0.0.0.0",
    port=8000,
)


# =====================================================================
# Task management tools
# =====================================================================


@mcp.tool()
def plan_task(
    title: Annotated[str, "Short task title"],
    goal: Annotated[str, "What success looks like for this task"],
    description: Annotated[str, "What needs to be done and why"] = "",
    done_criteria: Annotated[list[str], "Criteria that must be true when done"] | None = None,
) -> str:
    """Break a big task into small, ordered steps.

    Each step gets a clear goal and done-criteria so nothing is skipped.
    Use this FIRST when tackling any non-trivial work.
    """
    task = Task(
        title=title,
        description=description,
        value_hypothesis=goal,
        acceptance_criteria=done_criteria or [],
    )
    _kanban.add_tasks([task])
    _kanban.ready(task.id)
    return (
        f"Step added: '{task.title}' (id: {task.id})\n"
        f"Goal: {task.value_hypothesis}\n"
        f"Done criteria: {', '.join(task.acceptance_criteria) or 'none specified'}\n"
        f"Status: ready to start"
    )


@mcp.tool()
def next_step() -> str:
    """Get the next step to work on.

    Enforces focus: you must finish your current step before pulling a new one.
    Prevents multitasking and skipped steps.
    """
    task = _kanban.pull()
    if task is None:
        ready = _kanban.by_status(TaskStatus.READY)
        in_progress = _kanban.by_status(TaskStatus.IN_PROGRESS)
        if in_progress:
            t = in_progress[0]
            return (
                f"You already have a step in progress: '{t.title}' (id: {t.id})\n"
                f"Finish it first, then call next_step again."
            )
        if not ready:
            return "All steps are done or no steps planned. Use plan_task to add more."
        return "Finish your current step before pulling the next one."
    return (
        f"Next step: {task.title} (id: {task.id})\n"
        f"Description: {task.description}\n"
        f"Goal: {task.value_hypothesis}\n"
        f"Done criteria: {', '.join(task.acceptance_criteria) or 'none specified'}\n\n"
        f"Work on this ONE step. When finished, call mark_done."
    )


@mcp.tool()
def mark_done(
    task_id: Annotated[str, "ID of the step to mark done"],
    notes: Annotated[str, "What was done, files changed, etc."] = "",
) -> str:
    """Mark the current step as done after completing it.

    Only call this AFTER the work is actually finished and verified.
    """
    task = _kanban.submit_for_review(task_id)
    _kanban.approve(task_id)
    lead = task.lead_time_seconds
    time_str = f" (took {lead:.0f}s)" if lead else ""
    return f"Step '{task.title}' marked done{time_str}.\n{f'Notes: {notes}' if notes else ''}"


@mcp.tool()
def flag_problem(
    task_id: Annotated[str, "ID of the blocked step"],
    problem: Annotated[str, "What went wrong"],
    severity: Annotated[str, "How bad is it? critical/high/medium/low"],
    possible_causes: Annotated[list[str], "What might be causing this (2-5 hypotheses)"] | None = None,
    suggested_fix: Annotated[str, "Your best idea for fixing it"] = "",
) -> str:
    """Flag a problem or blocker on the current step.

    Stops work until the problem is analyzed and resolved.
    Use when something is broken, unclear, or risky.
    """
    _kanban.block(task_id, problem)

    lines = [f"BLOCKED: Step {task_id} — {problem}"]
    if severity == "critical":
        lines.insert(0, "CRITICAL — all work should stop until this is resolved.")
    lines.append(f"Severity: {severity}")
    if possible_causes:
        lines.append("Possible causes:")
        for i, c in enumerate(possible_causes, 1):
            lines.append(f"  {i}. {c}")
    if suggested_fix:
        lines.append(f"Suggested fix: {suggested_fix}")
    return "\n".join(lines)


@mcp.tool()
def resolve_problem(
    task_id: Annotated[str, "ID of the step to unblock"],
    resolution: Annotated[str, "How it was fixed"] = "",
) -> str:
    """Unblock a previously flagged step after fixing the problem."""
    _kanban.unblock(task_id)
    return f"Step {task_id} unblocked. {f'Resolution: {resolution}' if resolution else 'Ready to continue.'}"


# =====================================================================
# Progress tracking
# =====================================================================


@mcp.tool()
def show_progress() -> str:
    """Show the current status of all steps: done, in progress, blocked, and remaining."""
    tasks = _kanban.tasks
    if not tasks:
        return "No steps planned yet. Use plan_task to get started."

    done = _kanban.by_status(TaskStatus.DONE)
    in_progress = _kanban.by_status(TaskStatus.IN_PROGRESS)
    blocked = _kanban.by_status(TaskStatus.BLOCKED)
    ready = _kanban.by_status(TaskStatus.READY)
    backlog = _kanban.by_status(TaskStatus.BACKLOG)

    total = len(tasks)
    pct = (len(done) / total * 100) if total else 0
    bar_filled = int(pct / 5)
    bar = f"[{'#' * bar_filled}{'.' * (20 - bar_filled)}] {pct:.0f}%"

    lines = [f"## Progress: {len(done)}/{total} steps done", bar, ""]

    def _section(title: str, items: list[Task], emoji: str) -> None:
        if items:
            lines.append(f"**{emoji} {title}** ({len(items)})")
            for t in items:
                extra = f" — {t.blocked_reason}" if t.blocked_reason else ""
                lines.append(f"  [{t.id}] {t.title}{extra}")
            lines.append("")

    _section("In Progress", in_progress, ">>")
    _section("Blocked", blocked, "!!")
    _section("Ready", ready, "--")
    _section("Done", done, "OK")
    _section("Backlog", backlog, "..")

    return "\n".join(lines)


# =====================================================================
# Quality checks
# =====================================================================


@mcp.tool()
def check_quality(
    project_dir: Annotated[str, "Path to the project directory to check"],
) -> str:
    """Run automated quality checks (formatting, linting, tests).

    Use this before marking a step as done to catch issues early.
    """
    results: dict[str, str] = {}
    gates = [
        ("formatting", ["ruff", "format", "--check", "."]),
        ("linting", ["ruff", "check", "."]),
        ("tests", ["pytest", "--tb=short", "-q"]),
    ]
    all_ok = True
    for gname, cmd in gates:
        try:
            r = subprocess.run(cmd, cwd=project_dir, capture_output=True, text=True, timeout=120)
            passed = r.returncode == 0
            if passed:
                results[gname] = "PASS"
            else:
                output = (r.stdout[-300:] + r.stderr[-300:]).strip()
                results[gname] = f"FAIL\n{output}"
                all_ok = False
        except Exception as e:
            results[gname] = f"ERROR: {e}"
            all_ok = False

    header = "All checks passed — safe to proceed." if all_ok else "Some checks failed — fix before continuing."
    detail = "\n".join(f"  {k}: {v}" for k, v in results.items())
    return f"{header}\n{detail}"


@mcp.tool()
def review_work(
    task_id: Annotated[str, "ID of the step to review"],
    security: Annotated[float, "No vulnerabilities, secrets handled properly (0-1)"],
    quality: Annotated[float, "Clean code, tested, proper error handling (0-1)"],
    completeness: Annotated[float, "Meets all done-criteria (0-1)"],
    efficiency: Annotated[float, "No unnecessary complexity or waste (0-1)"],
    sustainability: Annotated[float, "Clean deps, good logging, maintainable (0-1)"],
) -> str:
    """Score completed work across 5 dimensions (SQDCE).

    Each dimension is 0-1, all must be >= 0.7 to pass.
    """
    scores = {
        "security": security,
        "quality": quality,
        "completeness": completeness,
        "efficiency": efficiency,
        "sustainability": sustainability,
    }
    failing = {k: v for k, v in scores.items() if v < 0.7}
    avg = sum(scores.values()) / len(scores)
    if failing:
        detail = ", ".join(f"{k}={v:.2f}" for k, v in failing.items())
        return (
            f"Review FAILED for step {task_id}.\n"
            f"Below threshold (0.7): {detail}\n"
            f"Average: {avg:.2f}\n"
            f"Fix the failing dimensions before marking done."
        )
    return (
        f"Review PASSED for step {task_id}.\n"
        f"Average score: {avg:.2f}. All dimensions >= 0.7."
    )


# =====================================================================
# Learning (kaizen)
# =====================================================================


@mcp.tool()
def log_lesson(
    category: Annotated[str, "Area: planning, coding, testing, process, tools"],
    what_happened: Annotated[str, "What went wrong or could be better"],
    do_instead: Annotated[str, "What to do differently next time"],
) -> str:
    """Record a lesson learned during this session.

    These accumulate over time so future sessions avoid the same mistakes.
    """
    kaizen_dir = Path(settings.obeya_dir) / "kaizen"
    kaizen_dir.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "category": category,
        "observation": what_happened,
        "improvement": do_instead,
    }
    log_path = kaizen_dir / "kaizen_log.jsonl"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return f"Lesson recorded: [{category}] {what_happened} -> {do_instead}"


@mcp.tool()
def past_lessons(
    category: Annotated[str, "Filter by area, or 'all'"] = "all",
    limit: Annotated[int, "Max lessons to return"] = 10,
) -> str:
    """Retrieve lessons learned from previous sessions to avoid repeating mistakes."""
    log_path = Path(settings.obeya_dir) / "kaizen" / "kaizen_log.jsonl"
    if not log_path.exists():
        return "No lessons recorded yet. Use log_lesson after discovering something useful."
    entries = []
    for line in log_path.read_text(encoding="utf-8").strip().splitlines():
        try:
            e = json.loads(line)
            if category == "all" or e["category"] == category:
                entries.append(e)
        except json.JSONDecodeError:
            continue
    recent = entries[-limit:]
    if not recent:
        return "No matching lessons."
    lines = [f"[{e['timestamp'][:10]}] {e['category']}: {e['observation']} -> {e['improvement']}" for e in recent]
    return "\n".join(lines)


# =====================================================================
# Problem analysis (PISCAR)
# =====================================================================


@mcp.tool()
def analyze_problem(
    problem: Annotated[str, "What's going wrong (be specific)"],
    possible_causes: Annotated[list[str], "3-7 hypotheses for why this is happening"],
    proposed_fix: Annotated[str, "First thing to try"],
    impact: Annotated[dict[str, str], "What's affected"] | None = None,
    expected_behavior: Annotated[str, "What should happen instead"] = "",
    success_criterion: Annotated[str, "How to know it's fixed"] = "",
) -> str:
    """Structured problem analysis (PISCAR framework).

    Define the problem, list possible causes, propose a fix, and set a success criterion.
    Use when stuck or when a task keeps failing.
    """
    analysis = PiscarAnalysis(
        problem=problem,
        impact=impact or {},
        standard=expected_behavior,
        causes=possible_causes,
        action=proposed_fix,
        expected_result=success_criterion,
    )
    return analysis.to_prompt_context()


# =====================================================================
# Server runners
# =====================================================================


def run_http(host: str = "0.0.0.0", port: int = 8000) -> None:
    """Start the MCP server as Streamable HTTP on the given host/port."""
    import sys

    # Override host/port on the settings object before running
    mcp.settings.host = host
    mcp.settings.port = port
    # Allow connections from any origin (needed for remote access / Claude Desktop)
    mcp.settings.transport_security = None

    print(f"Lean Tech MCP server running at http://{host}:{port}/mcp", file=sys.stderr)
    print("Add this URL as a custom connector in Claude Desktop.", file=sys.stderr)
    mcp.run(transport="streamable-http")


def run_stdio() -> None:
    """Start the MCP server on stdio (for Claude Desktop JSON config)."""
    import sys

    print("Starting Lean Tech MCP server (stdio)...", file=sys.stderr)
    mcp.run(transport="stdio")
