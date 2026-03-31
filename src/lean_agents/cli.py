"""Typer CLI for the Lean Tech Agents framework.

Usage:
    lean-agents run "Build a REST API for user management"
    lean-agents kanban
    lean-agents iterations
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer
from rich.console import Console

from lean_agents import __version__
from lean_agents.config import settings
from lean_agents.logging import setup_logging

app = typer.Typer(
    name="lean-agents",
    help="Lean Tech Agents — agentic template with Plan-Build-Review feedback loop.",
    no_args_is_help=True,
)
console = Console()


@app.callback()
def main(
    project_dir: Path = typer.Option(
        ".", "--project", "-p", help="Target project directory"
    ),
    log_level: str = typer.Option(
        "INFO", "--log-level", "-l", help="Log level (DEBUG, INFO, WARNING, ERROR)"
    ),
) -> None:
    """Configure global settings."""
    settings.project_dir = project_dir
    settings.log_level = log_level
    setup_logging()


@app.command()
def run(
    goal: str = typer.Argument(..., help="What to build — the customer goal"),
    max_iterations: int = typer.Option(
        5, "--max-iter", "-n", help="Max plan-build-review cycles"
    ),
    budget: float = typer.Option(
        5.0, "--budget", "-b", help="Max USD budget for this run"
    ),
) -> None:
    """Execute a full lean cycle: Plan -> Build -> Review."""
    settings.max_iterations = max_iterations
    settings.max_budget_usd = budget

    from lean_agents.orchestrator import Orchestrator

    orchestrator = Orchestrator()
    result = asyncio.run(orchestrator.run(goal))

    console.print(f"\n[bold green]Cycle complete.[/bold green]")
    console.print(f"  Iteration: {result.iteration_id}")
    console.print(f"  Tasks planned: {len(result.plan.tasks) if result.plan else 0}")
    console.print(f"  Builds: {len(result.builds)}")
    console.print(f"  Reviews: {len(result.reviews)}")
    console.print(f"  Defects: {result.total_defects}")
    console.print(f"  Rework cycles: {result.rework_count}")


@app.command()
def iterations(
    last: int = typer.Option(5, "--last", "-n", help="Show last N iterations"),
) -> None:
    """List recent iteration logs from the obeya."""
    from lean_agents.logging import display_iteration_summary
    from lean_agents.models import IterationLog

    iter_dir = Path(settings.iterations_dir)
    if not iter_dir.exists():
        console.print("[yellow]No iterations found yet.[/yellow]")
        raise typer.Exit()

    files = sorted(iter_dir.glob("iteration_*.json"), reverse=True)[:last]
    if not files:
        console.print("[yellow]No iteration logs found.[/yellow]")
        raise typer.Exit()

    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        log = IterationLog.model_validate(data)
        display_iteration_summary(log)


@app.command()
def serve() -> None:
    """Start the Lean Tech MCP server (stdio transport)."""
    import asyncio

    from lean_agents.mcp_server import run_server

    console.print("[bold cyan]Starting Lean Tech MCP server...[/bold cyan]")
    asyncio.run(run_server())


@app.command()
def version() -> None:
    """Show version."""
    console.print(f"lean-tech-agents v{__version__}")


if __name__ == "__main__":
    app()
