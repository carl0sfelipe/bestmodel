"""Redis Streams benchmark queue provider (plan decision 8).

The real queue connects lazily to Redis on the first publish so the application
starts without a running Redis service; tests substitute a fake queue.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from fastapi import Request


class BenchmarkQueue(ABC):
    """Publishes benchmark run events for the async validation worker."""

    @abstractmethod
    def publish(self, event: dict) -> None:
        """Push an event dict to the queue."""


class RedisStreamQueue(BenchmarkQueue):
    """Redis Streams queue whose connection is opened lazily on first publish."""

    STREAM_KEY = "benchmark_runs"

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._client = None

    def _connect(self):
        if self._client is None:
            import redis

            self._client = redis.Redis.from_url(self._redis_url)
        return self._client

    def publish(self, event: dict) -> None:
        self._connect().xadd(self.STREAM_KEY, event)


def get_benchmark_queue(request: Request) -> BenchmarkQueue:
    """FastAPI dependency resolving the configured benchmark queue."""
    return request.app.state.benchmark_queue
