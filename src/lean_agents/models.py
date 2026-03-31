"""Domain models for the Lean Tech Agents framework.

All inter-agent communication uses these typed models — never free text.
This enforces API-based communication (Lean Tech Principle 2).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TaskStatus(StrEnum):
    """Kanban column states — pull-based flow."""
    BACKLOG = "backlog"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    DONE = "done"
    BLOCKED = "blocked"


class Severity(StrEnum):
    """Defect severity for Jidoka stop-the-line decisions."""
    CRITICAL = "critical"   # Stop all work
    HIGH = "high"           # Stop related work
    MEDIUM = "medium"       # Fix before next pull
    LOW = "low"             # Queue for kaizen


class DetectionStage(StrEnum):
    """Where a defect was caught — earlier is better (shift-left)."""
    A_SELF_CHECK = "A"      # Agent self-check
    B_PIPELINE = "B"        # Automated CI/CD
    C_PEER_REVIEW = "C"     # Reviewer agent
    D_INTEGRATION = "D"     # Integration testing
    E_PRODUCTION = "E"      # Runtime / customer


class AgentRole(StrEnum):
    PLANNER = "planner"
    BUILDER = "builder"
    REVIEWER = "reviewer"
    ORCHESTRATOR = "orchestrator"


# ---------------------------------------------------------------------------
# Core task model
# ---------------------------------------------------------------------------

class Task(BaseModel):
    """A unit of work flowing through the kanban.

    Tracks value hypothesis, acceptance criteria, and lean metrics.
    """
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.BACKLOG
    value_hypothesis: str = ""
    acceptance_criteria: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    blocked_reason: str | None = None
    parent_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def lead_time_seconds(self) -> float | None:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


# ---------------------------------------------------------------------------
# Inter-agent message protocol
# ---------------------------------------------------------------------------

class AgentMessage(BaseModel):
    """Typed envelope for all agent-to-agent communication."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    from_agent: AgentRole
    to_agent: AgentRole
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload_type: str
    payload: dict[str, Any]


# ---------------------------------------------------------------------------
# Planner outputs
# ---------------------------------------------------------------------------

class PlanResult(BaseModel):
    """Output of the Planner agent — a decomposed, value-mapped task list."""
    goal: str
    tasks: list[Task]
    value_stream: str = ""
    assumptions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Builder outputs
# ---------------------------------------------------------------------------

class BuildResult(BaseModel):
    """Output of the Builder agent — what was built and how."""
    task_id: str
    files_changed: list[str] = Field(default_factory=list)
    commands_run: list[str] = Field(default_factory=list)
    tests_passed: bool = False
    notes: str = ""


# ---------------------------------------------------------------------------
# Reviewer outputs
# ---------------------------------------------------------------------------

class Defect(BaseModel):
    """A defect found during review — triggers Jidoka protocol."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    severity: Severity
    detection_stage: DetectionStage
    description: str
    root_cause: str = ""
    countermeasure: str = ""
    file_path: str | None = None
    line_number: int | None = None


class ReviewResult(BaseModel):
    """Output of the Reviewer agent — SQDCE quality assessment."""
    task_id: str
    approved: bool
    defects: list[Defect] = Field(default_factory=list)
    sqdce_scores: dict[str, float] = Field(default_factory=dict)
    improvement_suggestions: list[str] = Field(default_factory=list)
    notes: str = ""


# ---------------------------------------------------------------------------
# Iteration tracking (Obeya / visual management)
# ---------------------------------------------------------------------------

class IterationLog(BaseModel):
    """One complete plan-build-review cycle — persisted for kaizen."""
    iteration_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    goal: str = ""
    plan: PlanResult | None = None
    builds: list[BuildResult] = Field(default_factory=list)
    reviews: list[ReviewResult] = Field(default_factory=list)
    messages: list[AgentMessage] = Field(default_factory=list)
    kaizen_notes: list[str] = Field(default_factory=list)
    total_defects: int = 0
    rework_count: int = 0

    @property
    def cycle_time_seconds(self) -> float | None:
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
