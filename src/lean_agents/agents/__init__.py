"""Agent definitions — the Core Trio: Planner, Builder, Reviewer."""

from lean_agents.agents.base import AgentConfig, build_agent_options
from lean_agents.agents.planner import PLANNER_CONFIG, PLANNER_PROMPT
from lean_agents.agents.builder import BUILDER_CONFIG, BUILDER_PROMPT
from lean_agents.agents.reviewer import REVIEWER_CONFIG, REVIEWER_PROMPT

__all__ = [
    "AgentConfig",
    "build_agent_options",
    "PLANNER_CONFIG",
    "PLANNER_PROMPT",
    "BUILDER_CONFIG",
    "BUILDER_PROMPT",
    "REVIEWER_CONFIG",
    "REVIEWER_PROMPT",
]
