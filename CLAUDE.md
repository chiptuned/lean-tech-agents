# CLAUDE.md - Lean Tech Agents

## Project Overview

Agentic template implementing **lean principles** for AI agent orchestration.
Three-agent feedback loop: **Planner -> Builder -> Reviewer** with pull-based work, built-in quality (Jidoka), and continuous improvement (Kaizen).

## Architecture

```
Orchestrator (Pull System)
    |
    +-- Planner Agent   : Decomposes problem, creates value-mapped tasks
    +-- Builder Agent    : Implements one-piece-flow, stops at defects
    +-- Reviewer Agent   : Quality gates (SQDCE), root-cause analysis
    |
    +-- Obeya (Visual Management) : iteration logs in /obeya/
    +-- Kanban State              : pull-based task flow
```

## Development Standards

### Always Run Before Committing
```bash
ruff format .
ruff check . --fix
pytest
```

### Technology Stack
- **Package Manager**: uv (Astral)
- **Logging**: loguru + rich console
- **CLI**: typer
- **Models**: pydantic v2
- **Agent SDK**: claude-agent-sdk

## Key Lean Tech Principles (Agent-Adapted)

1. **Value for the Customer**: Every agent action maps to deliverable value
2. **Pull System**: Agents pull tasks from kanban, never pushed
3. **One-Piece Flow**: Complete one task fully before pulling next
4. **Jidoka**: Stop immediately on defect, analyze root cause
5. **Kaizen**: Each iteration produces improvement metrics
6. **PISCAR**: Problem -> Impact -> Standard -> Causes -> Action -> Result

## Agent Communication

Agents communicate via structured Pydantic models, not free text.
All inter-agent messages are logged to `/iterations/` for traceability.

## File References

- `src/lean_agents/orchestrator.py` : Main feedback loop
- `src/lean_agents/agents/planner.py` : Planning agent
- `src/lean_agents/agents/builder.py` : Building agent
- `src/lean_agents/agents/reviewer.py` : Review agent
- `src/lean_agents/lean/principles.py` : Lean principles as code
- `src/lean_agents/lean/kanban.py` : Pull system state machine
