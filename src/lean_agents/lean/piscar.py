"""PISCAR problem-solving framework for agents.

When an agent is blocked or a defect is found, PISCAR structures
the root-cause analysis and countermeasure design.

P - Problem:  Quantify the gap
I - Impact:   Effect on customer value (SQDCE dimensions)
S - Standard: What should happen vs. what does happen
C - Causes:   3-7 root cause hypotheses
A - Action:   Countermeasure to test
R - Result:   Expected outcome + success metric
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PiscarAnalysis(BaseModel):
    """Structured problem-solving output.

    Used by the Reviewer when defects are found,
    and by the Orchestrator when iterations stall.
    """

    problem: str = Field(
        ...,
        description="Quantified gap: what is vs. what should be, with numbers.",
    )
    impact: dict[str, str] = Field(
        default_factory=dict,
        description="SQDCE impact map: which dimensions are affected and how.",
    )
    standard: str = Field(
        default="",
        description="Description of the expected flow or behavior.",
    )
    causes: list[str] = Field(
        default_factory=list,
        min_length=1,
        max_length=7,
        description="3-7 root cause hypotheses (use 5 Whys to generate).",
    )
    action: str = Field(
        default="",
        description="First countermeasure to try.",
    )
    expected_result: str = Field(
        default="",
        description="Measurable success criterion for the countermeasure.",
    )

    def to_prompt_context(self) -> str:
        """Serialize to a string suitable for injection into agent prompts."""
        lines = [
            f"## PISCAR Analysis",
            f"**Problem**: {self.problem}",
        ]
        if self.impact:
            impacts = ", ".join(f"{k}: {v}" for k, v in self.impact.items())
            lines.append(f"**Impact (SQDCE)**: {impacts}")
        if self.standard:
            lines.append(f"**Standard**: {self.standard}")
        if self.causes:
            lines.append("**Root Causes**:")
            for i, c in enumerate(self.causes, 1):
                lines.append(f"  {i}. {c}")
        if self.action:
            lines.append(f"**Countermeasure**: {self.action}")
        if self.expected_result:
            lines.append(f"**Expected Result**: {self.expected_result}")
        return "\n".join(lines)
