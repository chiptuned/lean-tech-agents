"""Rich + Loguru logging setup for full iteration traceability.

Every agent action, message, and defect is logged with rich formatting
so you can reconstruct any iteration from the logs alone.
"""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from lean_agents.config import settings
from lean_agents.models import (
    AgentRole,
    BuildResult,
    Defect,
    IterationLog,
    PlanResult,
    ReviewResult,
    Severity,
    Task,
    TaskStatus,
)

console = Console(stderr=True)

# ---------------------------------------------------------------------------
# Loguru configuration
# ---------------------------------------------------------------------------

LOGURU_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{extra[agent]:>12}</cyan> | "
    "<level>{message}</level>"
)


def setup_logging() -> None:
    """Configure loguru with rich sink + optional file sink."""
    logger.remove()

    # Console sink via rich
    logger.add(
        sys.stderr,
        format=LOGURU_FORMAT,
        level=settings.log_level,
        colorize=True,
    )

    # File sink for full traceability
    if settings.log_to_file:
        log_path = settings.iterations_dir / "lean_agents.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        logger.add(
            str(log_path),
            format=LOGURU_FORMAT,
            level="DEBUG",
            rotation="10 MB",
            retention="30 days",
        )

    logger.configure(extra={"agent": "system"})


def get_agent_logger(role: AgentRole) -> logger:  # noqa: ANN204
    """Return a logger bound to a specific agent role."""
    return logger.bind(agent=role.value)


# ---------------------------------------------------------------------------
# Rich display helpers
# ---------------------------------------------------------------------------

_SEVERITY_COLORS = {
    Severity.CRITICAL: "bold red",
    Severity.HIGH: "red",
    Severity.MEDIUM: "yellow",
    Severity.LOW: "dim",
}

_STATUS_COLORS = {
    TaskStatus.BACKLOG: "dim",
    TaskStatus.READY: "cyan",
    TaskStatus.IN_PROGRESS: "blue",
    TaskStatus.REVIEW: "magenta",
    TaskStatus.DONE: "green",
    TaskStatus.BLOCKED: "bold red",
}


def display_plan(plan: PlanResult) -> None:
    """Render a plan as a rich panel with task table."""
    table = Table(title="Tasks", show_lines=True)
    table.add_column("#", width=4)
    table.add_column("Title", min_width=30)
    table.add_column("Status", width=14)
    table.add_column("Value Hypothesis", min_width=20)

    for i, task in enumerate(plan.tasks, 1):
        status_style = _STATUS_COLORS.get(task.status, "")
        table.add_row(
            str(i),
            task.title,
            Text(task.status.value, style=status_style),
            task.value_hypothesis or "-",
        )

    console.print(Panel(table, title=f"Plan: {plan.goal}", border_style="cyan"))

    if plan.risks:
        console.print(Panel(
            "\n".join(f"  - {r}" for r in plan.risks),
            title="Risks",
            border_style="yellow",
        ))


def display_build(result: BuildResult) -> None:
    """Render build result."""
    status = "[green]PASS[/green]" if result.tests_passed else "[red]FAIL[/red]"
    lines = [
        f"Task: {result.task_id}",
        f"Tests: {status}",
        f"Files changed: {len(result.files_changed)}",
    ]
    if result.files_changed:
        lines.extend(f"  - {f}" for f in result.files_changed)
    console.print(Panel("\n".join(lines), title="Build Result", border_style="blue"))


def display_review(result: ReviewResult) -> None:
    """Render review result with defects."""
    verdict = "[green]APPROVED[/green]" if result.approved else "[red]REJECTED[/red]"
    lines = [f"Task: {result.task_id}", f"Verdict: {verdict}"]

    if result.sqdce_scores:
        scores = " | ".join(f"{k}: {v:.1f}" for k, v in result.sqdce_scores.items())
        lines.append(f"SQDCE: {scores}")

    console.print(Panel("\n".join(lines), title="Review Result", border_style="magenta"))

    for defect in result.defects:
        style = _SEVERITY_COLORS.get(defect.severity, "")
        console.print(Panel(
            f"[{style}]{defect.severity.value.upper()}[/{style}] "
            f"(stage {defect.detection_stage.value})\n"
            f"{defect.description}\n"
            f"Root cause: {defect.root_cause or 'TBD'}\n"
            f"Countermeasure: {defect.countermeasure or 'TBD'}",
            title=f"Defect {defect.id}",
            border_style=style or "white",
        ))


def display_iteration_summary(log: IterationLog) -> None:
    """Render a full iteration summary for the Obeya board."""
    table = Table(title=f"Iteration {log.iteration_id}", show_lines=True)
    table.add_column("Metric", style="bold")
    table.add_column("Value")

    cycle = f"{log.cycle_time_seconds:.1f}s" if log.cycle_time_seconds else "in progress"
    table.add_row("Goal", log.goal)
    table.add_row("Cycle time", cycle)
    table.add_row("Builds", str(len(log.builds)))
    table.add_row("Reviews", str(len(log.reviews)))
    table.add_row("Defects found", str(log.total_defects))
    table.add_row("Rework cycles", str(log.rework_count))
    table.add_row("Messages exchanged", str(len(log.messages)))

    console.print(Panel(table, border_style="green"))

    if log.kaizen_notes:
        console.print(Panel(
            "\n".join(f"  - {n}" for n in log.kaizen_notes),
            title="Kaizen Notes",
            border_style="yellow",
        ))


def display_kanban(tasks: list[Task]) -> None:
    """Render current kanban board state."""
    table = Table(title="Kanban Board", show_lines=True)
    for status in TaskStatus:
        table.add_column(status.value, min_width=18)

    columns: dict[TaskStatus, list[str]] = {s: [] for s in TaskStatus}
    for task in tasks:
        columns[task.status].append(task.title)

    max_rows = max((len(v) for v in columns.values()), default=0)
    for i in range(max_rows):
        row = []
        for status in TaskStatus:
            items = columns[status]
            row.append(items[i] if i < len(items) else "")
        table.add_row(*row)

    console.print(table)
