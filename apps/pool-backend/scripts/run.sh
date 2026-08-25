#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

port=$(uv run python -c "import src.config; print(src.config.API_PORT)")

occupants=$(lsof -ti tcp:"$port" 2>/dev/null || true)
if [ -n "$occupants" ]; then
    echo "port $port is busy; occupying pid(s): $occupants" >&2
    exit 1
fi

exec uv run uvicorn src.main:app --host 127.0.0.1 --port "$port" --log-level warning
