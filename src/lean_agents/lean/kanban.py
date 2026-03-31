"""Pull-based kanban state machine for agent task flow.

Implements one-piece flow with WIP limits.
Agents PULL tasks — the orchestrator never pushes.
"""

from __future__ import annotations

from datetime import datetime, timezone

from loguru import logger

from lean_agents.config import settings
from lean_agents.models import Task, TaskStatus


class KanbanBoard:
    """Minimal kanban with strict WIP limits and pull semantics.

    State transitions:
        BACKLOG -> READY -> IN_PROGRESS -> REVIEW -> DONE
                                      |          ^
                                      v          |
                                    BLOCKED -----+  (unblock triggers re-review)
                                      |
                                      +-> IN_PROGRESS  (rework)
    """

    def __init__(self, wip_limit: int | None = None) -> None:
        self._tasks: dict[str, Task] = {}
        self._wip_limit = wip_limit or settings.wip_limit
        self._log = logger.bind(agent="kanban")

    # --- Queries ---

    @property
    def tasks(self) -> list[Task]:
        return list(self._tasks.values())

    def by_status(self, status: TaskStatus) -> list[Task]:
        return [t for t in self._tasks.values() if t.status == status]

    @property
    def in_progress_count(self) -> int:
        return len(self.by_status(TaskStatus.IN_PROGRESS))

    @property
    def has_capacity(self) -> bool:
        return self.in_progress_count < self._wip_limit

    # --- Mutations ---

    def add_tasks(self, tasks: list[Task]) -> None:
        """Add tasks to backlog."""
        for task in tasks:
            task.status = TaskStatus.BACKLOG
            self._tasks[task.id] = task
            self._log.info(f"Added to backlog: {task.title} [{task.id}]")

    def ready(self, task_id: str) -> Task:
        """Mark task as ready to be pulled."""
        task = self._get(task_id)
        self._transition(task, TaskStatus.READY)
        return task

    def pull(self) -> Task | None:
        """Agent pulls next ready task. Returns None if WIP limit reached."""
        if not self.has_capacity:
            self._log.warning(
                f"WIP limit reached ({self._wip_limit}). "
                "Complete current work before pulling."
            )
            return None

        ready = self.by_status(TaskStatus.READY)
        if not ready:
            self._log.info("No tasks ready to pull.")
            return None

        task = ready[0]
        self._transition(task, TaskStatus.IN_PROGRESS)
        task.started_at = datetime.now(timezone.utc)
        return task

    def submit_for_review(self, task_id: str) -> Task:
        """Builder submits completed work for review."""
        task = self._get(task_id)
        self._transition(task, TaskStatus.REVIEW)
        return task

    def approve(self, task_id: str) -> Task:
        """Reviewer approves — task is DONE."""
        task = self._get(task_id)
        self._transition(task, TaskStatus.DONE)
        task.completed_at = datetime.now(timezone.utc)
        lead = task.lead_time_seconds
        if lead is not None:
            self._log.info(f"Task {task_id} done. Lead time: {lead:.1f}s")
        return task

    def reject(self, task_id: str, reason: str = "") -> Task:
        """Reviewer rejects — task goes back to IN_PROGRESS for rework."""
        task = self._get(task_id)
        self._transition(task, TaskStatus.IN_PROGRESS)
        self._log.warning(f"Rejected {task_id}: {reason}")
        return task

    def block(self, task_id: str, reason: str) -> Task:
        """Jidoka: stop the line."""
        task = self._get(task_id)
        task.blocked_reason = reason
        self._transition(task, TaskStatus.BLOCKED)
        return task

    def unblock(self, task_id: str) -> Task:
        """Resume blocked task."""
        task = self._get(task_id)
        task.blocked_reason = None
        self._transition(task, TaskStatus.IN_PROGRESS)
        return task

    # --- Internals ---

    def _get(self, task_id: str) -> Task:
        if task_id not in self._tasks:
            msg = f"Task {task_id} not found on board."
            raise KeyError(msg)
        return self._tasks[task_id]

    _VALID_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
        TaskStatus.BACKLOG: {TaskStatus.READY},
        TaskStatus.READY: {TaskStatus.IN_PROGRESS},
        TaskStatus.IN_PROGRESS: {TaskStatus.REVIEW, TaskStatus.BLOCKED},
        TaskStatus.REVIEW: {TaskStatus.DONE, TaskStatus.IN_PROGRESS},
        TaskStatus.BLOCKED: {TaskStatus.IN_PROGRESS},
        TaskStatus.DONE: set(),
    }

    def _transition(self, task: Task, to: TaskStatus) -> None:
        allowed = self._VALID_TRANSITIONS.get(task.status, set())
        if to not in allowed:
            msg = f"Invalid transition: {task.status.value} -> {to.value} for task {task.id}"
            raise ValueError(msg)
        self._log.debug(f"[{task.id}] {task.status.value} -> {to.value}")
        task.status = to
