#!/usr/bin/env bash
# ComfyUI server lifecycle for the pack: start refuses a busy port, stop kills
# only the PID we started (never a generic pkill).
set -euo pipefail

PACK_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMFY_ROOT="/Users/mini/ComfyUI"
PORT=8188
PID_FILE="$PACK_ROOT/data/comfy-server.pid"
LOG_FILE="$PACK_ROOT/data/comfy-server.log"

start() {
  local busy_pid
  busy_pid="$(lsof -i ":$PORT" -sTCP:LISTEN -t 2>/dev/null | head -1 || true)"
  if [ -n "$busy_pid" ]; then
    echo "port $PORT busy (pid $busy_pid); refusing to start" >&2
    exit 1
  fi
  mkdir -p "$PACK_ROOT/data"
  (cd "$COMFY_ROOT" && nohup ./venv/bin/python main.py --listen 127.0.0.1 --port "$PORT" >"$LOG_FILE" 2>&1 &
   echo $! >"$PID_FILE")
  for _ in $(seq 1 60); do
    if curl -s --max-time 2 "http://127.0.0.1:$PORT/system_stats" >/dev/null; then
      echo "comfyui up (pid $(cat "$PID_FILE"))"
      return 0
    fi
    sleep 1
  done
  echo "server did not answer /system_stats within 60s; see $LOG_FILE" >&2
  exit 1
}

stop() {
  if [ ! -f "$PID_FILE" ]; then
    echo "no pid file at $PID_FILE; nothing to stop" >&2
    return 0
  fi
  local pid
  pid="$(cat "$PID_FILE")"
  if kill "$pid" 2>/dev/null; then
    echo "stopped pid $pid"
  else
    echo "pid $pid not running (stale pid file)" >&2
  fi
  rm -f "$PID_FILE"
}

case "${1:-}" in
  start) start ;;
  stop) stop ;;
  *) echo "usage: comfy-server.sh start|stop" >&2; exit 1 ;;
esac
