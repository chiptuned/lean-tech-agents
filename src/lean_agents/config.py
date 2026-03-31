"""Configuration for the Lean Tech Agents framework.

Uses pydantic-settings for env-var + .env support.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global configuration — overridable via env vars or .env file."""

    model_config = SettingsConfigDict(
        env_prefix="LEAN_AGENTS_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # --- API ---
    anthropic_api_key: str = ""

    # --- Agent models ---
    planner_model: str = "sonnet"
    builder_model: str = "sonnet"
    reviewer_model: str = "sonnet"
    orchestrator_model: str = "opus"

    # --- Limits ---
    max_iterations: int = Field(default=5, description="Max plan-build-review cycles")
    max_turns_per_agent: int = Field(default=25, description="Max SDK turns per agent call")
    max_budget_usd: float = Field(default=5.0, description="Total budget cap per run")
    wip_limit: int = Field(default=1, description="One-piece flow — max concurrent tasks")

    # --- Paths ---
    project_dir: Path = Field(default=Path("."), description="Root of the target project")
    iterations_dir: Path = Field(default=Path("iterations"), description="Iteration log output")
    obeya_dir: Path = Field(default=Path("obeya"), description="Visual management output")

    # --- Quality thresholds ---
    min_sqdce_score: float = Field(default=0.7, description="Minimum SQDCE score to pass review")
    jidoka_stop_on_critical: bool = Field(default=True, description="Halt all work on critical defect")

    # --- Logging ---
    log_level: str = "INFO"
    log_to_file: bool = True
    rich_tracebacks: bool = True


settings = Settings()
