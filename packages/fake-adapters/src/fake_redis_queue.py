"""In-memory benchmark queue used by tests (fake adapter)."""

from __future__ import annotations

from src.dependencies.redis_queue_provider import BenchmarkQueue


class FakeRedisQueue(BenchmarkQueue):
    def __init__(self) -> None:
        self.events: list[dict] = []

    def publish(self, event: dict) -> None:
        self.events.append(dict(event))
