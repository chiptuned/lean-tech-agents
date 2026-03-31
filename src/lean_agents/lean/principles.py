"""Lean principles adapted for AI agent orchestration.

These are not guidelines — they are executable constraints.
The orchestrator enforces them at every state transition.

Key twist: optimized for agent throughput, not human cognitive load.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lean_agents.models import (
        Defect,
        IterationLog,
        ReviewResult,
        Severity,
        Task,
    )


# ---------------------------------------------------------------------------
# Principle 1: Value for the Customer
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ValuePrinciple:
    """Every agent action must map to deliverable customer value.

    Agent adaptation:
    - Agents don't "go and see" — they analyze artifacts directly.
    - Value hypothesis is required metadata on every task.
    - SQDCE scoring replaces subjective quality judgment.
    """
    name: str = "Value for the Customer"

    @staticmethod
    def validate_task_has_value(task: Task) -> bool:
        """Reject tasks without explicit value hypothesis."""
        return bool(task.value_hypothesis.strip())

    @staticmethod
    def validate_sqdce_scores(scores: dict[str, float], threshold: float = 0.7) -> bool:
        """All SQDCE dimensions must meet threshold."""
        required = {"safety", "quality", "delivery", "cost", "environment"}
        present = set(scores.keys())
        if not required.issubset(present):
            return False
        return all(v >= threshold for v in scores.values())


# ---------------------------------------------------------------------------
# Principle 2: Tech-Enabled Network of Teams (Agents)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NetworkPrinciple:
    """Agents communicate via typed APIs, not free text.

    Agent adaptation:
    - Pydantic models ARE the API contracts.
    - Each agent owns its domain — no cross-domain tool access.
    - PISCAR is the universal problem-solving protocol.
    """
    name: str = "Tech-Enabled Network of Agents"

    @staticmethod
    def validate_api_contract(payload: dict) -> bool:
        """Ensure inter-agent payloads have required fields."""
        return "payload_type" in payload and "payload" in payload


# ---------------------------------------------------------------------------
# Principle 3: Right-First-Time and Just-in-Time
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class QualityFlowPrinciple:
    """Built-in quality + continuous flow — the two sides of lean delivery.

    Agent adaptation:
    - Jidoka: orchestrator halts pipeline on critical defects.
    - One-piece flow: WIP limit of 1 task per agent.
    - Pull system: agents request work, orchestrator never pushes.
    - Takt time: measured as cycle_time per iteration.
    """
    name: str = "Right-First-Time & Just-in-Time"

    @staticmethod
    def should_stop_line(defects: list[Defect]) -> bool:
        """Jidoka: return True if any defect is critical."""
        from lean_agents.models import Severity
        return any(d.severity == Severity.CRITICAL for d in defects)

    @staticmethod
    def check_wip_limit(in_progress_count: int, limit: int = 1) -> bool:
        """One-piece flow: reject if WIP exceeds limit."""
        return in_progress_count <= limit

    @staticmethod
    def should_rework(review: ReviewResult) -> bool:
        """Return True if review rejected — triggers builder rework."""
        return not review.approved


# ---------------------------------------------------------------------------
# Principle 4: Building a Learning Organization
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LearningPrinciple:
    """Every iteration produces structured learning artifacts.

    Agent adaptation:
    - Kaizen notes are mandatory outputs of every review.
    - Iteration logs are the "Obeya" — visual management for agents.
    - Defect patterns are analyzed across iterations for systemic fixes.
    """
    name: str = "Building a Learning Organization"

    @staticmethod
    def extract_kaizen_notes(log: IterationLog) -> list[str]:
        """Derive improvement notes from iteration data."""
        notes: list[str] = []

        if log.rework_count > 0:
            notes.append(
                f"Rework happened {log.rework_count}x — "
                "investigate if planner decomposition was too coarse."
            )

        if log.total_defects > 3:
            notes.append(
                f"{log.total_defects} defects found — "
                "consider adding poka-yoke (automated checks) to builder."
            )

        cycle = log.cycle_time_seconds
        if cycle and cycle > 120:
            notes.append(
                f"Cycle time {cycle:.0f}s is high — "
                "check if tasks can be decomposed smaller."
            )

        return notes


# ---------------------------------------------------------------------------
# Aggregate — the four pillars
# ---------------------------------------------------------------------------

LEAN_PRINCIPLES = (
    ValuePrinciple(),
    NetworkPrinciple(),
    QualityFlowPrinciple(),
    LearningPrinciple(),
)
