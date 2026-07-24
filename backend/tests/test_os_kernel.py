from __future__ import annotations

from app.os import GenieOSKernel, TaskStatus
from app.os.permissions import SideEffectLevel


def test_kernel_records_user_turn_lifecycle():
    kernel = GenieOSKernel()

    task = kernel.begin_user_turn(
        session_id="session-1",
        input_text="Open Chrome and search Genie OS",
        source="test",
    )

    assert task.status == TaskStatus.RUNNING
    assert task.task_id.startswith("task_")
    assert task.trace_id.startswith("trace_")

    completed = kernel.complete_task(task.task_id, {"reply_length": 12})

    assert completed is not None
    assert completed.status == TaskStatus.COMPLETED
    assert completed.result["reply_length"] == 12
    assert [event.type for event in kernel.events.for_task(task.task_id)] == [
        "task.started",
        "input.text.received",
        "task.completed",
    ]


def test_kernel_failure_records_error_event():
    kernel = GenieOSKernel()
    task = kernel.begin_user_turn(session_id="s", input_text="fail", source="test")

    failed = kernel.fail_task(task.task_id, "boom")

    assert failed is not None
    assert failed.status == TaskStatus.FAILED
    assert failed.error == "boom"
    assert kernel.events.for_task(task.task_id)[-1].payload["error"] == "boom"


def test_kernel_records_checkpoints_and_permissions():
    kernel = GenieOSKernel()
    task = kernel.begin_user_turn(session_id="s", input_text="delete a file", source="test")

    checkpoint = kernel.record_checkpoint(
        task.task_id,
        label="planned",
        state={"steps": ["inspect", "confirm", "execute"]},
    )
    permission = kernel.request_permission(
        risk=SideEffectLevel.DESTRUCTIVE,
        description="Delete file",
        source="test",
        task_id=task.task_id,
        payload={"path": "C:/tmp/example.txt"},
    )
    decided = kernel.decide_permission(permission.request_id, approved=False, reason="test")

    assert checkpoint.checkpoint_id.startswith("chk_")
    assert kernel.checkpoints.latest(task.task_id) == checkpoint
    assert decided is not None
    assert decided.status == "denied"
    assert kernel.events.for_task(task.task_id)[-2].type == "permission.required"
    assert kernel.events.for_task(task.task_id)[-1].type == "permission.decided"
