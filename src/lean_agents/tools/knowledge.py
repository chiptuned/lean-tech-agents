"""Knowledge management tools — Kaizen tracking and learning distribution."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from claude_agent_sdk import tool

from lean_agents.config import settings


@tool(
    "record_kaizen",
    "Record a kaizen (improvement) note to the knowledge base",
    {"category": str, "observation": str, "improvement": str},
)
async def record_kaizen(args: dict[str, Any]) -> dict[str, Any]:
    """Persist a kaizen observation for future agent reference."""
    kaizen_dir = settings.obeya_dir / "kaizen"
    kaizen_dir.mkdir(parents=True, exist_ok=True)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "category": args["category"],
        "observation": args["observation"],
        "improvement": args["improvement"],
    }

    # Append to kaizen log
    log_path = kaizen_dir / "kaizen_log.jsonl"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    return {
        "content": [
            {"type": "text", "text": f"Kaizen recorded: {args['category']}"}
        ]
    }


@tool(
    "get_kaizen_history",
    "Retrieve recent kaizen notes for a given category or all categories",
    {"category": str, "limit": int},
)
async def get_kaizen_history(args: dict[str, Any]) -> dict[str, Any]:
    """Read kaizen history for learning distribution."""
    log_path = settings.obeya_dir / "kaizen" / "kaizen_log.jsonl"

    if not log_path.exists():
        return {"content": [{"type": "text", "text": "No kaizen history yet."}]}

    entries = []
    for line in log_path.read_text(encoding="utf-8").strip().splitlines():
        try:
            entry = json.loads(line)
            if args["category"] == "all" or entry["category"] == args["category"]:
                entries.append(entry)
        except json.JSONDecodeError:
            continue

    limit = args.get("limit", 10)
    recent = entries[-limit:]

    if not recent:
        return {"content": [{"type": "text", "text": "No matching kaizen notes."}]}

    lines = []
    for e in recent:
        lines.append(
            f"[{e['timestamp'][:10]}] {e['category']}: "
            f"{e['observation']} -> {e['improvement']}"
        )

    return {"content": [{"type": "text", "text": "\n".join(lines)}]}
