"""Tests for the scheduler's APScheduler executor adapter."""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from types import SimpleNamespace

from infrastructure.scheduling.scheduler.apscheduler_executor import (
    ScheduledThreadPoolExecutor,
)


class _FakeScheduler:
    def _create_lock(self) -> threading.RLock:
        return threading.RLock()

    def _dispatch_event(self, _event: object) -> None:
        return None


def test_worker_receives_exact_fire_time_without_submission_listener() -> None:
    started = threading.Event()
    release = threading.Event()
    observed: list[datetime] = []
    scheduled_run_time = datetime(2026, 1, 15, 9, 0, tzinfo=UTC)

    def callback(*, scheduled_run_time: datetime) -> None:
        observed.append(scheduled_run_time)
        started.set()
        assert release.wait(5)

    job = SimpleNamespace(
        id="task-1",
        max_instances=1,
        misfire_grace_time=None,
        func=callback,
        args=(),
        kwargs={},
        _jobstore_alias="default",
    )
    executor = ScheduledThreadPoolExecutor(max_workers=1)
    executor.start(_FakeScheduler(), "default")
    try:
        executor.submit_job(job, [scheduled_run_time])
        assert started.wait(5)
        assert observed == [scheduled_run_time]
    finally:
        release.set()
        executor.shutdown(wait=True)
