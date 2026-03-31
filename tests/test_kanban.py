"""Tests for the kanban pull system."""

from __future__ import annotations

import pytest

from lean_agents.lean.kanban import KanbanBoard
from lean_agents.models import Task, TaskStatus


@pytest.fixture
def board() -> KanbanBoard:
    return KanbanBoard(wip_limit=1)


@pytest.fixture
def sample_tasks() -> list[Task]:
    return [
        Task(title="Task A", value_hypothesis="Delivers value A"),
        Task(title="Task B", value_hypothesis="Delivers value B"),
    ]


class TestKanbanBoard:
    def test_add_tasks_to_backlog(self, board: KanbanBoard, sample_tasks: list[Task]) -> None:
        board.add_tasks(sample_tasks)
        assert len(board.by_status(TaskStatus.BACKLOG)) == 2

    def test_ready_transitions_from_backlog(
        self, board: KanbanBoard, sample_tasks: list[Task]
    ) -> None:
        board.add_tasks(sample_tasks)
        task = board.ready(sample_tasks[0].id)
        assert task.status == TaskStatus.READY

    def test_pull_respects_wip_limit(
        self, board: KanbanBoard, sample_tasks: list[Task]
    ) -> None:
        board.add_tasks(sample_tasks)
        board.ready(sample_tasks[0].id)
        board.ready(sample_tasks[1].id)

        # First pull succeeds
        task = board.pull()
        assert task is not None
        assert task.status == TaskStatus.IN_PROGRESS

        # Second pull blocked by WIP limit
        task2 = board.pull()
        assert task2 is None

    def test_full_lifecycle(self, board: KanbanBoard, sample_tasks: list[Task]) -> None:
        board.add_tasks([sample_tasks[0]])
        board.ready(sample_tasks[0].id)

        task = board.pull()
        assert task is not None

        board.submit_for_review(task.id)
        assert task.status == TaskStatus.REVIEW

        board.approve(task.id)
        assert task.status == TaskStatus.DONE
        assert task.lead_time_seconds is not None

    def test_reject_sends_back_to_in_progress(
        self, board: KanbanBoard, sample_tasks: list[Task]
    ) -> None:
        board.add_tasks([sample_tasks[0]])
        board.ready(sample_tasks[0].id)
        board.pull()
        board.submit_for_review(sample_tasks[0].id)

        board.reject(sample_tasks[0].id, "Needs rework")
        assert sample_tasks[0].status == TaskStatus.IN_PROGRESS

    def test_block_and_unblock(self, board: KanbanBoard, sample_tasks: list[Task]) -> None:
        board.add_tasks([sample_tasks[0]])
        board.ready(sample_tasks[0].id)
        board.pull()

        board.block(sample_tasks[0].id, "Critical defect")
        assert sample_tasks[0].status == TaskStatus.BLOCKED
        assert sample_tasks[0].blocked_reason == "Critical defect"

        board.unblock(sample_tasks[0].id)
        assert sample_tasks[0].status == TaskStatus.IN_PROGRESS
        assert sample_tasks[0].blocked_reason is None

    def test_invalid_transition_raises(
        self, board: KanbanBoard, sample_tasks: list[Task]
    ) -> None:
        board.add_tasks([sample_tasks[0]])
        with pytest.raises(ValueError, match="Invalid transition"):
            board.approve(sample_tasks[0].id)  # Can't approve from backlog


class TestPrinciples:
    def test_value_validation(self) -> None:
        from lean_agents.lean.principles import ValuePrinciple

        task_with_value = Task(title="T", value_hypothesis="Delivers X")
        task_without = Task(title="T", value_hypothesis="")

        assert ValuePrinciple.validate_task_has_value(task_with_value)
        assert not ValuePrinciple.validate_task_has_value(task_without)

    def test_sqdce_validation(self) -> None:
        from lean_agents.lean.principles import ValuePrinciple

        good = {"safety": 0.9, "quality": 0.8, "delivery": 0.9, "cost": 0.8, "environment": 0.9}
        bad = {"safety": 0.9, "quality": 0.5, "delivery": 0.9, "cost": 0.8, "environment": 0.9}
        incomplete = {"safety": 0.9, "quality": 0.8}

        assert ValuePrinciple.validate_sqdce_scores(good)
        assert not ValuePrinciple.validate_sqdce_scores(bad)
        assert not ValuePrinciple.validate_sqdce_scores(incomplete)

    def test_jidoka_stop_line(self) -> None:
        from lean_agents.lean.principles import QualityFlowPrinciple
        from lean_agents.models import Defect, DetectionStage, Severity

        critical = [Defect(severity=Severity.CRITICAL, detection_stage=DetectionStage.C_PEER_REVIEW, description="Broken")]
        low = [Defect(severity=Severity.LOW, detection_stage=DetectionStage.C_PEER_REVIEW, description="Minor")]

        assert QualityFlowPrinciple.should_stop_line(critical)
        assert not QualityFlowPrinciple.should_stop_line(low)
