"""MCP Server for Lean Tech Agents.

Exposes task management, quality checks, and progress tracking
as an MCP server that any Claude Code or Cowork instance can connect to.

The user-facing tools use plain language. The lean engine
(kanban, Jidoka, SQDCE, PISCAR) runs under the hood.

Run directly:
    uv run lean-agents serve

Or configure in Claude Desktop / Claude Code:
    {
        "mcpServers": {
            "lean-agents": {
                "command": "uv",
                "args": ["run", "--from", "lean-tech-agents", "lean-agents", "serve"]
            }
        }
    }
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from lean_agents.config import settings
from lean_agents.lean.kanban import KanbanBoard
from lean_agents.lean.piscar import PiscarAnalysis
from lean_agents.models import Task, TaskStatus

# ---------------------------------------------------------------------------
# Global state (lives for the MCP session)
# ---------------------------------------------------------------------------

_kanban = KanbanBoard()

# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

server = Server("lean-tech-agents")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Expose tools to the connected Claude instance."""
    return [
        # ----- Task management (user-facing) -----
        Tool(
            name="plan_task",
            description=(
                "Break a big task into small, ordered steps. "
                "Each step gets a clear goal and done-criteria so nothing is skipped. "
                "Use this FIRST when tackling any non-trivial work."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Short task title"},
                    "description": {"type": "string", "description": "What needs to be done and why"},
                    "goal": {
                        "type": "string",
                        "description": "What success looks like for this task",
                    },
                    "done_criteria": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of criteria that must be true when this step is done",
                    },
                },
                "required": ["title", "goal"],
            },
        ),
        Tool(
            name="next_step",
            description=(
                "Get the next step to work on. Enforces focus: "
                "you must finish your current step before pulling a new one. "
                "Prevents multitasking and skipped steps."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="mark_done",
            description=(
                "Mark the current step as done after completing it. "
                "Only call this AFTER the work is actually finished and verified."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "ID of the step to mark done"},
                    "notes": {"type": "string", "description": "What was done, files changed, etc."},
                },
                "required": ["task_id"],
            },
        ),
        Tool(
            name="flag_problem",
            description=(
                "Flag a problem or blocker on the current step. "
                "Stops work until the problem is analyzed and resolved. "
                "Use when something is broken, unclear, or risky."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "ID of the blocked step"},
                    "problem": {"type": "string", "description": "What went wrong"},
                    "severity": {
                        "type": "string",
                        "enum": ["critical", "high", "medium", "low"],
                        "description": "How bad is it? Critical = everything stops",
                    },
                    "possible_causes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "What might be causing this (list 2-5 hypotheses)",
                    },
                    "suggested_fix": {"type": "string", "description": "Your best idea for fixing it"},
                },
                "required": ["task_id", "problem", "severity"],
            },
        ),
        Tool(
            name="resolve_problem",
            description="Unblock a previously flagged step after fixing the problem.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "ID of the step to unblock"},
                    "resolution": {"type": "string", "description": "How it was fixed"},
                },
                "required": ["task_id"],
            },
        ),

        # ----- Progress tracking -----
        Tool(
            name="show_progress",
            description=(
                "Show the current status of all steps: what's done, what's in progress, "
                "what's blocked, and what's left. Use this to stay oriented."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),

        # ----- Quality checks -----
        Tool(
            name="check_quality",
            description=(
                "Run automated quality checks on the project (formatting, linting, tests). "
                "Use this before marking a step as done to catch issues early."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "project_dir": {
                        "type": "string",
                        "description": "Path to the project directory to check",
                    },
                },
                "required": ["project_dir"],
            },
        ),
        Tool(
            name="review_work",
            description=(
                "Score completed work across 5 dimensions: Security, Quality, Completeness, "
                "Efficiency, and Sustainability. Each dimension is 0-1, all must be >= 0.7 to pass."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "security": {
                        "type": "number", "minimum": 0, "maximum": 1,
                        "description": "No vulnerabilities, secrets handled properly",
                    },
                    "quality": {
                        "type": "number", "minimum": 0, "maximum": 1,
                        "description": "Clean code, tested, proper error handling",
                    },
                    "completeness": {
                        "type": "number", "minimum": 0, "maximum": 1,
                        "description": "Meets all done-criteria",
                    },
                    "efficiency": {
                        "type": "number", "minimum": 0, "maximum": 1,
                        "description": "No unnecessary complexity or waste",
                    },
                    "sustainability": {
                        "type": "number", "minimum": 0, "maximum": 1,
                        "description": "Clean deps, good logging, maintainable",
                    },
                },
                "required": ["task_id", "security", "quality", "completeness", "efficiency", "sustainability"],
            },
        ),

        # ----- Learning -----
        Tool(
            name="log_lesson",
            description=(
                "Record a lesson learned during this session. "
                "These accumulate over time so future sessions avoid the same mistakes."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "What area (planning, coding, testing, process, tools)",
                    },
                    "what_happened": {"type": "string", "description": "What went wrong or could be better"},
                    "do_instead": {"type": "string", "description": "What to do differently next time"},
                },
                "required": ["category", "what_happened", "do_instead"],
            },
        ),
        Tool(
            name="past_lessons",
            description="Retrieve lessons learned from previous sessions to avoid repeating mistakes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Filter by area, or 'all'",
                        "default": "all",
                    },
                    "limit": {"type": "integer", "default": 10},
                },
            },
        ),

        # ----- Problem analysis -----
        Tool(
            name="analyze_problem",
            description=(
                "Structured problem analysis: define the problem, list possible causes, "
                "propose a fix, and set a success criterion. "
                "Use when stuck or when a task keeps failing."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "problem": {"type": "string", "description": "What's going wrong (be specific)"},
                    "impact": {
                        "type": "object",
                        "description": "What's affected (e.g., {'security': 'exposed API keys', 'users': 'login broken'})",
                        "additionalProperties": {"type": "string"},
                    },
                    "expected_behavior": {"type": "string", "description": "What should happen instead"},
                    "possible_causes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "3-7 hypotheses for why this is happening",
                    },
                    "proposed_fix": {"type": "string", "description": "First thing to try"},
                    "success_criterion": {"type": "string", "description": "How to know it's fixed"},
                },
                "required": ["problem", "possible_causes", "proposed_fix"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool invocations."""
    try:
        result = await _dispatch(name, arguments)
        return [TextContent(type="text", text=result)]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {e}")]


async def _dispatch(name: str, args: dict[str, Any]) -> str:
    """Route tool calls to lean engine handlers."""

    # --- Task management (maps to kanban under the hood) ---
    if name == "plan_task":
        task = Task(
            title=args["title"],
            description=args.get("description", ""),
            value_hypothesis=args.get("goal", ""),
            acceptance_criteria=args.get("done_criteria", []),
        )
        _kanban.add_tasks([task])
        _kanban.ready(task.id)
        return (
            f"Step added: '{task.title}' (id: {task.id})\n"
            f"Goal: {task.value_hypothesis}\n"
            f"Done criteria: {', '.join(task.acceptance_criteria) or 'none specified'}\n"
            f"Status: ready to start"
        )

    if name == "next_step":
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

    if name == "mark_done":
        tid = args["task_id"]
        notes = args.get("notes", "")
        task = _kanban.submit_for_review(tid)
        _kanban.approve(tid)
        lead = task.lead_time_seconds
        time_str = f" (took {lead:.0f}s)" if lead else ""
        return f"Step '{task.title}' marked done{time_str}.\n{f'Notes: {notes}' if notes else ''}"

    if name == "flag_problem":
        tid = args["task_id"]
        problem = args["problem"]
        severity = args["severity"]
        causes = args.get("possible_causes", [])
        fix = args.get("suggested_fix", "")

        _kanban.block(tid, problem)

        lines = [f"BLOCKED: Step {tid} — {problem}"]
        if severity == "critical":
            lines.insert(0, "CRITICAL — all work should stop until this is resolved.")
        lines.append(f"Severity: {severity}")
        if causes:
            lines.append("Possible causes:")
            for i, c in enumerate(causes, 1):
                lines.append(f"  {i}. {c}")
        if fix:
            lines.append(f"Suggested fix: {fix}")
        return "\n".join(lines)

    if name == "resolve_problem":
        tid = args["task_id"]
        resolution = args.get("resolution", "")
        _kanban.unblock(tid)
        return f"Step {tid} unblocked. {f'Resolution: {resolution}' if resolution else 'Ready to continue.'}"

    # --- Progress tracking ---
    if name == "show_progress":
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

    # --- Quality checks ---
    if name == "check_quality":
        project_dir = args["project_dir"]
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

    if name == "review_work":
        scores = {
            "security": args["security"],
            "quality": args["quality"],
            "completeness": args["completeness"],
            "efficiency": args["efficiency"],
            "sustainability": args["sustainability"],
        }
        failing = {k: v for k, v in scores.items() if v < 0.7}
        avg = sum(scores.values()) / len(scores)
        if failing:
            detail = ", ".join(f"{k}={v:.2f}" for k, v in failing.items())
            return (
                f"Review FAILED for step {args['task_id']}.\n"
                f"Below threshold (0.7): {detail}\n"
                f"Average: {avg:.2f}\n"
                f"Fix the failing dimensions before marking done."
            )
        return (
            f"Review PASSED for step {args['task_id']}.\n"
            f"Average score: {avg:.2f}. All dimensions >= 0.7."
        )

    # --- Learning (kaizen under the hood) ---
    if name == "log_lesson":
        kaizen_dir = Path(settings.obeya_dir) / "kaizen"
        kaizen_dir.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "category": args["category"],
            "observation": args["what_happened"],
            "improvement": args["do_instead"],
        }
        log_path = kaizen_dir / "kaizen_log.jsonl"
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        return f"Lesson recorded: [{args['category']}] {args['what_happened']} -> {args['do_instead']}"

    if name == "past_lessons":
        log_path = Path(settings.obeya_dir) / "kaizen" / "kaizen_log.jsonl"
        if not log_path.exists():
            return "No lessons recorded yet. Use log_lesson after discovering something useful."
        entries = []
        category = args.get("category", "all")
        for line in log_path.read_text(encoding="utf-8").strip().splitlines():
            try:
                e = json.loads(line)
                if category == "all" or e["category"] == category:
                    entries.append(e)
            except json.JSONDecodeError:
                continue
        limit = args.get("limit", 10)
        recent = entries[-limit:]
        if not recent:
            return "No matching lessons."
        lines = [f"[{e['timestamp'][:10]}] {e['category']}: {e['observation']} -> {e['improvement']}" for e in recent]
        return "\n".join(lines)

    # --- Problem analysis (PISCAR under the hood) ---
    if name == "analyze_problem":
        analysis = PiscarAnalysis(
            problem=args["problem"],
            impact=args.get("impact", {}),
            standard=args.get("expected_behavior", ""),
            causes=args["possible_causes"],
            action=args["proposed_fix"],
            expected_result=args.get("success_criterion", ""),
        )
        return analysis.to_prompt_context()

    return f"Unknown tool: {name}"


async def run_server() -> None:
    """Start the MCP server on stdio."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
