"""FastAPI application entry point.

Wires routes and dependency providers. Providers are stored on ``app.state``
and resolved lazily by FastAPI dependencies so the application starts even when
external services (Postgres, Redis, artifact storage) are unavailable.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI

from src.dependencies.artifact_vault_provider import LocalArtifactVault
from src.dependencies.database_session_provider import DatabaseSessionProvider
from src.dependencies.redis_queue_provider import RedisStreamQueue
from src.routes import (
    benchmark_submission_route,
    hardware_match_route,
    leaderboard_route,
    model_match_route,
)

DEFAULT_DATABASE_URL = "postgresql://bestmodel:bestmodel@localhost:5434/bestmodel"
DEFAULT_REDIS_URL = "redis://localhost:6380/0"
DEFAULT_ARTIFACT_VAULT_DIR = "./artifacts"


def create_app() -> FastAPI:
    app = FastAPI(title="bestmodel Public API", version="0.1.0")
    app.state.database_provider = DatabaseSessionProvider(
        os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    )
    app.state.artifact_vault = LocalArtifactVault(
        Path(os.environ.get("ARTIFACT_VAULT_DIR", DEFAULT_ARTIFACT_VAULT_DIR))
    )
    app.state.benchmark_queue = RedisStreamQueue(
        os.environ.get("REDIS_URL", DEFAULT_REDIS_URL)
    )
    app.include_router(hardware_match_route.router)
    app.include_router(model_match_route.router)
    app.include_router(leaderboard_route.router)
    app.include_router(benchmark_submission_route.router)
    return app


app = create_app()
