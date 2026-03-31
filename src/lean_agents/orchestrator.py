"""Orchestrator — the lean feedback loop engine.

Implements the Plan -> Build -> Review cycle with:
- Pull-based kanban flow
- Jidoka (stop-the-line on critical defects)
- Rework loops (reviewer rejects -> builder retries)
- Kaizen (iteration logs + improvement notes)
- Budget guards (cost ceiling per run)

The orchestrator is the "supportive team leader" from Lean Tech:
competent (understands the domain), caring (enables agents),
and structured (enforces lean constraints).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

from lean_agents.agents.base import AgentConfig, build_agent_options
from lean_agents.agents.builder import BUILDER_CONFIG
from lean_agents.agents.planner import PLANNER_CONFIG
from lean_agents.agents.reviewer import REVIEWER_CONFIG
from lean_agents.config import settings
from lean_agents.lean.kanban import KanbanBoard
from lean_agents.lean.principles import LearningPrinciple, QualityFlowPrinciple, ValuePrinciple
from lean_agents.logging import (
    display_build,
    display_iteration_summary,
    display_kanban,
    display_plan,
    display_review,
    get_agent_logger,
)
from lean_agents.models import (
    AgentMessage,
    AgentRole,
    BuildResult,
    IterationLog,
    PlanResult,
    ReviewResult,
    Task,
    TaskStatus,
)


class Orchestrator:
    """Lean feedback loop: Plan -> Build -> Review -> (Rework | Done).

    Usage:
        orchestrator = Orchestrator()
        result = await orchestrator.run("Build a REST API for user management")
    """

    def __init__(self) -> None:
        self._log = get_agent_logger(AgentRole.ORCHESTRATOR)
        self._kanban = KanbanBoard()
        self._iteration: IterationLog | None = None
        self._total_cost: float = 0.0

    async def run(self, goal: str) -> IterationLog:
        """Execute the full lean cycle for a given goal.

        1. Planner decomposes the goal into tasks
        2. For each task (pulled from kanban):
           a. Builder implements it
           b. Reviewer assesses quality
           c. If rejected: rework (back to builder)
           d. If approved: mark done, pull next
        3. Produce iteration log with kaizen notes
        """
        self._iteration = IterationLog(goal=goal)
        self._log.info(f"Starting lean cycle: {goal}")

        # --- Phase 1: Plan ---
        plan = await self._run_planner(goal)
        self._iteration.plan = plan
        display_plan(plan)

        # Validate value hypotheses
        for task in plan.tasks:
            if not ValuePrinciple.validate_task_has_value(task):
                self._log.warning(
                    f"Task '{task.title}' has no value hypothesis — adding placeholder."
                )
                task.value_hypothesis = f"Contributes to: {goal}"

        # Load tasks into kanban
        self._kanban.add_tasks(plan.tasks)
        for task in plan.tasks:
            self._kanban.ready(task.id)

        display_kanban(self._kanban.tasks)

        # --- Phase 2: Build + Review loop (one-piece flow) ---
        max_rework = 3
        while True:
            task = self._kanban.pull()
            if task is None:
                # No more tasks ready or WIP limit reached
                remaining = self._kanban.by_status(TaskStatus.READY)
                if not remaining:
                    break
                self._log.info("Waiting for current task to complete...")
                continue

            self._log.info(f"Pulled task: {task.title} [{task.id}]")

            rework_count = 0
            while rework_count <= max_rework:
                # Build
                build_result = await self._run_builder(task)
                self._iteration.builds.append(build_result)
                display_build(build_result)

                if not build_result.tests_passed:
                    # Jidoka: builder flagged a critical issue
                    self._log.warning(f"Builder flagged issue on {task.id}")
                    if rework_count >= max_rework:
                        self._kanban.block(task.id, "Max rework exceeded")
                        break
                    rework_count += 1
                    self._iteration.rework_count += 1
                    continue

                # Submit for review
                self._kanban.submit_for_review(task.id)

                # Review
                review_result = await self._run_reviewer(task, build_result)
                self._iteration.reviews.append(review_result)
                self._iteration.total_defects += len(review_result.defects)
                display_review(review_result)

                # Jidoka: check for critical defects
                if QualityFlowPrinciple.should_stop_line(review_result.defects):
                    self._log.error("JIDOKA: Critical defect — stopping the line!")
                    self._kanban.block(task.id, "Critical defect found")
                    break

                if review_result.approved:
                    self._kanban.approve(task.id)
                    self._log.info(f"Task {task.id} approved and done.")
                    break
                else:
                    # Reject -> rework
                    self._kanban.reject(task.id, "Review rejected")
                    rework_count += 1
                    self._iteration.rework_count += 1
                    if rework_count > max_rework:
                        self._kanban.block(task.id, "Max rework exceeded")
                        break
                    self._log.warning(
                        f"Rework #{rework_count} for {task.id}"
                    )

            display_kanban(self._kanban.tasks)

            # Budget guard
            if self._total_cost >= settings.max_budget_usd:
                self._log.warning(
                    f"Budget limit reached (${self._total_cost:.2f}). Stopping."
                )
                break

        # --- Phase 3: Kaizen ---
        self._iteration.completed_at = datetime.now(timezone.utc)
        kaizen = LearningPrinciple.extract_kaizen_notes(self._iteration)
        self._iteration.kaizen_notes = kaizen
        display_iteration_summary(self._iteration)

        # Persist iteration log
        self._save_iteration_log()

        return self._iteration

    # ------------------------------------------------------------------
    # Agent runners
    # ------------------------------------------------------------------

    async def _run_planner(self, goal: str) -> PlanResult:
        """Invoke the Planner agent and parse its output."""
        self._log.info("Invoking Planner agent...")
        prompt = f"Decompose this goal into tasks:\n\n{goal}"

        raw = await self._invoke_agent(PLANNER_CONFIG, prompt)
        plan_data = self._parse_json(raw)

        tasks = [
            Task(
                title=t.get("title", "Untitled"),
                description=t.get("description", ""),
                value_hypothesis=t.get("value_hypothesis", ""),
                acceptance_criteria=t.get("acceptance_criteria", []),
            )
            for t in plan_data.get("tasks", [])
        ]

        return PlanResult(
            goal=plan_data.get("goal", goal),
            tasks=tasks,
            value_stream=plan_data.get("value_stream", ""),
            assumptions=plan_data.get("assumptions", []),
            risks=plan_data.get("risks", []),
        )

    async def _run_builder(self, task: Task) -> BuildResult:
        """Invoke the Builder agent on a single task."""
        self._log.info(f"Invoking Builder for task: {task.title}")
        prompt = (
            f"Implement this task:\n\n"
            f"**Task ID**: {task.id}\n"
            f"**Title**: {task.title}\n"
            f"**Description**: {task.description}\n"
            f"**Value Hypothesis**: {task.value_hypothesis}\n"
            f"**Acceptance Criteria**:\n"
            + "\n".join(f"  - {c}" for c in task.acceptance_criteria)
        )

        raw = await self._invoke_agent(BUILDER_CONFIG, prompt)
        data = self._parse_json(raw)

        return BuildResult(
            task_id=data.get("task_id", task.id),
            files_changed=data.get("files_changed", []),
            commands_run=data.get("commands_run", []),
            tests_passed=data.get("tests_passed", False),
            notes=data.get("notes", ""),
        )

    async def _run_reviewer(self, task: Task, build: BuildResult) -> ReviewResult:
        """Invoke the Reviewer agent on completed work."""
        self._log.info(f"Invoking Reviewer for task: {task.title}")
        prompt = (
            f"Review the work done on this task:\n\n"
            f"**Task ID**: {task.id}\n"
            f"**Title**: {task.title}\n"
            f"**Acceptance Criteria**:\n"
            + "\n".join(f"  - {c}" for c in task.acceptance_criteria)
            + f"\n\n**Files changed**: {', '.join(build.files_changed)}\n"
            f"**Builder notes**: {build.notes}\n"
        )

        raw = await self._invoke_agent(REVIEWER_CONFIG, prompt)
        data = self._parse_json(raw)

        defects = [
            {
                "severity": d.get("severity", "low"),
                "detection_stage": d.get("detection_stage", "C"),
                "description": d.get("description", ""),
                "root_cause": d.get("root_cause", ""),
                "countermeasure": d.get("countermeasure", ""),
                "file_path": d.get("file_path"),
                "line_number": d.get("line_number"),
            }
            for d in data.get("defects", [])
        ]

        from lean_agents.models import Defect, DetectionStage, Severity

        typed_defects = []
        for d in defects:
            try:
                typed_defects.append(Defect(
                    severity=Severity(d["severity"]),
                    detection_stage=DetectionStage(d["detection_stage"]),
                    description=d["description"],
                    root_cause=d.get("root_cause", ""),
                    countermeasure=d.get("countermeasure", ""),
                    file_path=d.get("file_path"),
                    line_number=d.get("line_number"),
                ))
            except (ValueError, KeyError):
                self._log.warning(f"Skipping malformed defect: {d}")

        return ReviewResult(
            task_id=data.get("task_id", task.id),
            approved=data.get("approved", False),
            defects=typed_defects,
            sqdce_scores=data.get("sqdce_scores", {}),
            improvement_suggestions=data.get("improvement_suggestions", []),
            notes=data.get("notes", ""),
        )

    # ------------------------------------------------------------------
    # SDK invocation
    # ------------------------------------------------------------------

    async def _invoke_agent(self, config: AgentConfig, prompt: str) -> str:
        """Call the Claude Agent SDK and collect the final text output."""
        from claude_agent_sdk import AssistantMessage, ResultMessage, query

        options = build_agent_options(config)
        collected_text: list[str] = []

        self._log.debug(f"SDK call: role={config.role.value}, model={config.model}")

        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if hasattr(block, "text"):
                        collected_text.append(block.text)
                    elif hasattr(block, "name"):
                        self._log.debug(f"Tool used: {block.name}")
            elif isinstance(message, ResultMessage):
                if message.total_cost_usd:
                    self._total_cost += message.total_cost_usd
                    self._log.info(
                        f"Agent {config.role.value} cost: "
                        f"${message.total_cost_usd:.4f} "
                        f"(total: ${self._total_cost:.4f})"
                    )

        # Record message in iteration log
        if self._iteration:
            self._iteration.messages.append(AgentMessage(
                from_agent=config.role,
                to_agent=AgentRole.ORCHESTRATOR,
                payload_type="response",
                payload={"text": "\n".join(collected_text)},
            ))

        return "\n".join(collected_text)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any]:
        """Extract JSON from agent response (may be wrapped in markdown)."""
        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Extract from ```json ... ``` blocks
        import re
        match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Last resort: find first { ... } block
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass

        logger.warning("Could not parse JSON from agent response. Returning empty dict.")
        return {}

    def _save_iteration_log(self) -> None:
        """Persist iteration log as JSON for kaizen analysis."""
        if not self._iteration:
            return

        out_dir = Path(settings.iterations_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        filename = (
            f"iteration_{self._iteration.iteration_id}_"
            f"{self._iteration.started_at.strftime('%Y%m%d_%H%M%S')}.json"
        )
        path = out_dir / filename

        path.write_text(
            self._iteration.model_dump_json(indent=2),
            encoding="utf-8",
        )
        self._log.info(f"Iteration log saved: {path}")
