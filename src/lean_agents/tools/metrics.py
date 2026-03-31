"""SQDCE metrics collection and visualization tools."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from claude_agent_sdk import tool

from lean_agents.config import settings


@tool(
    "collect_sqdce_metrics",
    "Collect and display SQDCE metrics from iteration logs",
    {"iterations_dir": str},
)
async def collect_sqdce_metrics(args: dict[str, Any]) -> dict[str, Any]:
    """Aggregate SQDCE scores across recent iterations for trend analysis."""
    iter_dir = Path(args.get("iterations_dir", str(settings.iterations_dir)))

    if not iter_dir.exists():
        return {"content": [{"type": "text", "text": "No iteration logs found."}]}

    files = sorted(iter_dir.glob("iteration_*.json"), reverse=True)[:10]
    if not files:
        return {"content": [{"type": "text", "text": "No iteration logs found."}]}

    metrics: list[dict[str, Any]] = []
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        reviews = data.get("reviews", [])
        for review in reviews:
            scores = review.get("sqdce_scores", {})
            if scores:
                metrics.append({
                    "iteration": data.get("iteration_id", "?"),
                    "task": review.get("task_id", "?"),
                    "scores": scores,
                    "approved": review.get("approved", False),
                })

    if not metrics:
        return {"content": [{"type": "text", "text": "No SQDCE data in logs."}]}

    # Compute averages
    all_scores: dict[str, list[float]] = {}
    for m in metrics:
        for k, v in m["scores"].items():
            all_scores.setdefault(k, []).append(v)

    averages = {k: sum(v) / len(v) for k, v in all_scores.items()}
    summary = "\n".join(f"  {k}: {v:.2f}" for k, v in averages.items())

    return {
        "content": [
            {
                "type": "text",
                "text": (
                    f"SQDCE Averages (last {len(files)} iterations):\n{summary}\n"
                    f"Total reviews: {len(metrics)}"
                ),
            }
        ]
    }
