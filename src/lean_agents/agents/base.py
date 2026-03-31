"""Base agent configuration and SDK option builder.

Each agent in the Core Trio shares:
- Typed Pydantic I/O contracts
- Lean principle guardrails
- Structured logging via loguru
- Budget + turn limits from config
"""

from __future__ import annotations

from dataclasses import dataclass, field

from claude_agent_sdk import ClaudeAgentOptions

from lean_agents.config import settings
from lean_agents.models import AgentRole


@dataclass
class AgentConfig:
    """Declarative agent definition."""
    role: AgentRole
    model: str
    system_prompt: str
    allowed_tools: list[str] = field(default_factory=list)
    max_turns: int | None = None
    max_budget_usd: float | None = None
    permission_mode: str = "acceptEdits"


def build_agent_options(config: AgentConfig) -> ClaudeAgentOptions:
    """Convert an AgentConfig into SDK-ready ClaudeAgentOptions."""
    return ClaudeAgentOptions(
        system_prompt=config.system_prompt,
        model=config.model,
        allowed_tools=config.allowed_tools,
        permission_mode=config.permission_mode,
        max_turns=config.max_turns or settings.max_turns_per_agent,
        max_budget_usd=config.max_budget_usd or (settings.max_budget_usd / 3),
        cwd=str(settings.project_dir),
    )
