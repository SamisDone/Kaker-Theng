"""One heavy job at a time, everything else waits in line.

The server is small: processing two photos at once could run it out of
memory. Jobs go into a queue that a single worker thread drains. Clients poll
a job and are told how many people are ahead of them. When the line is full
they get a clear message instead of a failure halfway through.
"""

from __future__ import annotations

import secrets
import threading
import time
import traceback
from collections import deque
from dataclasses import dataclass, field
from typing import Callable

from .scan import ScanError

JOB_TTL_S = 3600


class QueueFull(Exception):
    pass


@dataclass
class Job:
    id: str
    kind: str
    fn: Callable[[], dict] = field(repr=False)
    status: str = "queued"  # queued | working | done | error
    result: dict | None = None
    error: dict | None = None
    created: float = field(default_factory=time.time)
    finished: float | None = None


class JobQueue:
    def __init__(self, max_waiting: int = 12):
        self.max_waiting = max_waiting
        self._waiting: deque[Job] = deque()
        self._jobs: dict[str, Job] = {}
        self._running: Job | None = None
        self._cv = threading.Condition()
        self._worker = threading.Thread(target=self._run, name="job-worker", daemon=True)
        self._worker.start()

    def submit(self, kind: str, fn: Callable[[], dict]) -> Job:
        with self._cv:
            if len(self._waiting) >= self.max_waiting:
                raise QueueFull()
            job = Job(secrets.token_urlsafe(9), kind, fn)
            self._jobs[job.id] = job
            self._waiting.append(job)
            self._cv.notify()
            return job

    def ahead(self, job: Job) -> int:
        """People ahead of this job: the one being worked on, and those
        waiting in front of it."""
        with self._cv:
            if job.status != "queued":
                return 0
            index = next((i for i, j in enumerate(self._waiting) if j is job), 0)
            return index + (1 if self._running else 0)

    def get(self, job_id: str) -> Job | None:
        with self._cv:
            return self._jobs.get(job_id)

    def waiting(self) -> int:
        with self._cv:
            return len(self._waiting) + (1 if self._running else 0)

    def _run(self):
        while True:
            with self._cv:
                while not self._waiting:
                    self._cv.wait(timeout=60)
                    self._prune()
                job = self._waiting.popleft()
                job.status = "working"
                self._running = job
            try:
                job.result = job.fn()
                job.status = "done"
            except ScanError as err:
                job.error = err.to_dict()
                job.status = "error"
            except Exception:  # noqa: BLE001 - report, keep the worker alive
                traceback.print_exc()
                job.error = {
                    "code": "internal",
                    "message": "Something went wrong on our side. Please try again.",
                    "message_bn": "আমাদের দিকে কিছু একটা গোলমাল হয়েছে। আবার চেষ্টা করুন।",
                }
                job.status = "error"
            finally:
                job.fn = None  # let the photo bytes go
                job.finished = time.time()
                with self._cv:
                    self._running = None

    def _prune(self):
        now = time.time()
        for job_id in [j.id for j in self._jobs.values() if j.finished and now - j.finished > JOB_TTL_S]:
            del self._jobs[job_id]
