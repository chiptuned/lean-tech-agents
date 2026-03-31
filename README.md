# Lean Tech Agents

An MCP server + agent template that helps Claude handle big tasks properly: break them down, work through them one at a time, check quality, and learn from mistakes.

No skipped steps. No half-done work. No "I'll fix that later."

## What It Does

You give Claude a complex task. Instead of attempting everything at once (and missing things), the system:

1. **Plans** — breaks the task into small, ordered steps with clear done-criteria
2. **Focuses** — works on ONE step at a time (no multitasking, no skipping ahead)
3. **Checks** — runs quality gates (formatting, linting, tests) before moving on
4. **Stops on problems** — flags blockers instead of working around them
5. **Learns** — records lessons so future sessions avoid the same mistakes

Under the hood it uses lean manufacturing principles (kanban, one-piece flow, stop-the-line), but you don't need to know any of that.

## Quick Start

### As an MCP server (Claude Code / Cowork / Claude Desktop)

```bash
# Install
uv tool install lean-tech-agents
# or from source:
git clone https://github.com/YOUR_USER/lean-tech-agents && cd lean-tech-agents && uv sync
```

Add to your Claude config:
```json
{
  "mcpServers": {
    "lean-agents": {
      "command": "uv",
      "args": ["run", "--from", "lean-tech-agents", "lean-agents", "serve"]
    }
  }
}
```

### As a CLI

```bash
lean-agents run "Build a REST API for user management" --budget 5.0
lean-agents iterations --last 5
lean-agents serve  # start MCP server
```

### As a Python library

```python
import asyncio
from lean_agents.orchestrator import Orchestrator

async def main():
    orchestrator = Orchestrator()
    result = await orchestrator.run("Add authentication to the API")
    print(f"Done in {result.cycle_time_seconds:.0f}s, {result.rework_count} reworks")

asyncio.run(main())
```

## MCP Tools

Once connected, Claude gets these tools:

| Tool | What it does |
|------|-------------|
| `plan_task` | Add a step with a goal and done-criteria |
| `next_step` | Get the next step to work on (blocks multitasking) |
| `mark_done` | Mark a step as finished |
| `show_progress` | See what's done, in progress, blocked, and remaining |
| `flag_problem` | Stop work on a step and log what went wrong |
| `resolve_problem` | Unblock a step after fixing the issue |
| `check_quality` | Run formatting, linting, and tests |
| `review_work` | Score work on 5 dimensions (all must pass >= 0.7) |
| `analyze_problem` | Structured root-cause analysis when stuck |
| `log_lesson` | Record what went wrong for future reference |
| `past_lessons` | Check previous lessons before starting |

## How It Works Internally

The user-friendly tools map to lean manufacturing concepts under the hood:

| User sees | Engine uses |
|-----------|-------------|
| `plan_task` / `next_step` | Kanban board with WIP limit = 1 (one-piece flow) |
| `flag_problem` | Jidoka (stop the line on defects) |
| `check_quality` | Poka-Yoke (mistake-proofing via automated checks) |
| `review_work` | SQDCE scoring (Safety, Quality, Delivery, Cost, Environment) |
| `analyze_problem` | PISCAR framework (Problem, Impact, Standard, Causes, Action, Result) |
| `log_lesson` | Kaizen (continuous improvement) |

## Project Structure

```
lean-tech-agents/
├── pyproject.toml                     # uv project (Python 3.13+)
├── CLAUDE.md                          # Claude Code project config
├── .claude/agents/                    # Claude Code subagent definitions
│   ├── planner.md                     # Breaks down goals
│   ├── builder.md                     # Implements one step
│   └── reviewer.md                    # Checks quality
├── src/lean_agents/
│   ├── mcp_server.py                  # MCP server (main entry point)
│   ├── cli.py                         # Typer CLI
│   ├── orchestrator.py                # Plan-Build-Review feedback loop
│   ├── models.py                      # Pydantic domain models
│   ├── config.py                      # Settings (env vars / .env)
│   ├── logging.py                     # Rich + Loguru logging
│   ├── agents/                        # Agent prompts + configs
│   ├── tools/                         # SDK-style MCP tools
│   └── lean/                          # Lean engine (kanban, principles)
├── iterations/                        # Iteration logs (JSON)
├── obeya/                             # Lessons learned (JSONL)
└── tests/
```

## Configuration

Environment variables (prefix `LEAN_AGENTS_`) or `.env` file:

```env
LEAN_AGENTS_ANTHROPIC_API_KEY=sk-ant-...
LEAN_AGENTS_MAX_BUDGET_USD=5.0
LEAN_AGENTS_WIP_LIMIT=1
LEAN_AGENTS_LOG_LEVEL=INFO
```

## Extending

**Add a step type**: create `src/lean_agents/agents/your_agent.py` + `.claude/agents/your_agent.md`

**Add a tool**: add handler to `mcp_server.py` `list_tools()` and `_dispatch()`

**Scale**: increase `WIP_LIMIT` for parallel work streams

## Inspired By

- Lean manufacturing (Toyota Production System)
- [Claude Agent SDK](https://platform.claude.com/docs/en/agent-sdk/overview)
