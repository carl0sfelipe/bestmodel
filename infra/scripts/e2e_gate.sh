#!/usr/bin/env bash
# Phase 0 integration gate: infra -> data -> tests -> CLI -> API -> worker -> leaderboard.
# Prints a command-by-command checklist and exits non-zero on any failure.
set -u

cd "$(dirname "$0")/../.."
WORK="$(mktemp -d)"
API_PORT=8012
export DATABASE_URL="postgresql://bestmodel:bestmodel@localhost:5434/bestmodel"
export REDIS_URL="redis://localhost:6380/0"
export ARTIFACT_VAULT_DIR="$WORK/artifacts"
export BENCHMARK_PROBE_KEY_PATH="$WORK/gate-key.pem"
export PATH="$HOME/.cargo/bin:$PATH"

FAILED=0
pass() { echo "PASS  $1"; }
fail() { echo "FAIL  $1"; FAILED=1; }
check_exit() { if [ "$1" -eq 0 ]; then pass "$2"; else fail "$2"; fi }
pg() { docker compose -f infra/docker/docker-compose.yml exec -T postgres psql -U bestmodel -d bestmodel -Atc "$1"; }

API_PID=""
WORKER_PID=""
# Kill leftovers from interrupted gate runs: stale workers/API would steal
# stream messages or the port.
pkill -f "src.worker" 2>/dev/null || true
lsof -nP -iTCP:"$API_PORT" -sTCP:LISTEN -t 2>/dev/null | xargs kill 2>/dev/null || true
sleep 1
cleanup() {
  [ -n "$API_PID" ] && kill "$API_PID" 2>/dev/null
  [ -n "$WORKER_PID" ] && kill "$WORKER_PID" 2>/dev/null
}
trap cleanup EXIT

echo "=== 1. Infrastructure ==="
docker compose -f infra/docker/docker-compose.yml up -d postgres redis >/dev/null 2>&1
READY=1
for _ in $(seq 1 45); do
  if docker compose -f infra/docker/docker-compose.yml exec -T postgres pg_isready -U bestmodel -d bestmodel >/dev/null 2>&1; then READY=0; break; fi
  sleep 2
done
check_exit "$READY" "docker compose up -d (postgres ready on 5434)"
docker compose -f infra/docker/docker-compose.yml up -d minio meilisearch >/dev/null 2>&1 || true

echo "=== 2. Migrations and seed ==="
make migrate >/dev/null 2>&1; check_exit "$?" "make migrate (exit 0)"
make seed >/dev/null 2>&1; check_exit "$?" "make seed (exit 0)"
GPU_COUNT=$(pg "SELECT count(*) FROM gpu_model;")
MODEL_COUNT=$(pg "SELECT count(*) FROM model_release;")
[ "${GPU_COUNT:-0}" -ge 20 ] && pass "gpu_model count >= 20 (got $GPU_COUNT)" || fail "gpu_model count >= 20 (got ${GPU_COUNT:-0})"
[ "${MODEL_COUNT:-0}" -ge 50 ] && pass "model_release count >= 50 (got $MODEL_COUNT)" || fail "model_release count >= 50 (got ${MODEL_COUNT:-0})"
CROSS=$(pg "SELECT count(*) FROM model_release m CROSS JOIN gpu_model g LIMIT 1;")
[ "${CROSS:-0}" -ge 1 ] && pass "model x gpu cross query returns rows" || fail "model x gpu cross query"

echo "=== 3. Test suites ==="
make test >/dev/null 2>&1; check_exit "$?" "make test (pytest green)"
(cd cli/benchmark-probe && cargo test --quiet >/dev/null 2>&1); check_exit "$?" "cargo test (green)"

echo "=== 4. CLI report generation (one internal machine) ==="
(cd cli/benchmark-probe && cargo build --quiet >/dev/null 2>&1); check_exit "$?" "cargo build benchmark-probe"
PROMPT_TOKENS=$((RANDOM % 900 + 100))
CONTEXT_TOKENS=$((RANDOM % 3000 + 4100))
./target/debug/benchmark-probe --runtime mock --report-runtime llama_cpp --prompt-tokens "$PROMPT_TOKENS" --context-tokens "$CONTEXT_TOKENS" --output "$WORK/benchmark-report.json" >/dev/null 2>&1
check_exit "$?" "benchmark-probe --runtime mock --output (per-machine command; 1/10 executed here)"
[ -s "$WORK/benchmark-report.json" ] && [ -s "$WORK/benchmark-report.signature" ] && pass "report + signature files produced" || fail "report files missing"

uv run python - "$BENCHMARK_PROBE_KEY_PATH" "$WORK/gate-key.pub.pem" <<'EOF'
import sys
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import load_pem_private_key
key = load_pem_private_key(open(sys.argv[1], "rb").read(), password=None)
open(sys.argv[2], "wb").write(key.public_key().public_bytes(
    serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
EOF
check_exit "$?" "trusted public key derived for the API"

echo "=== 5. API and worker ==="
TRUSTED_ED25519_PUBLIC_KEY_PATH="$WORK/gate-key.pub.pem" PYTHONPATH=apps/public-api \
  uv run uvicorn src.main:app --port "$API_PORT" --log-level warning >"$WORK/api.log" 2>&1 &
API_PID=$!
READY=1
for _ in $(seq 1 30); do
  curl -sf "http://localhost:$API_PORT/v1/submissions/nonce" >/dev/null 2>&1 && READY=0 && break
  sleep 1
done
check_exit "$READY" "uvicorn src.main:app --port $API_PORT (nonce endpoint ready)"

(cd apps/intake-worker && PYTHONPATH=src uv run python -m src.worker >"$WORK/worker.log" 2>&1) &
WORKER_PID=$!
sleep 2
kill -0 "$WORKER_PID" 2>/dev/null && pass "intake worker started (apps/intake-worker, python -m src.worker)" || fail "intake worker crashed on start (see $WORK/worker.log)"

echo "=== 6. Upload and leaderboard ==="
NONCE=$(curl -sf "http://localhost:$API_PORT/v1/submissions/nonce" | uv run python -c "import json,sys; print(json.load(sys.stdin)['challenge_nonce'])")
UPLOAD=$(curl -s -o "$WORK/upload.json" -w "%{http_code}" -X POST "http://localhost:$API_PORT/v1/submissions" \
  -F "report=<$WORK/benchmark-report.json" \
  -F "signature=$(cat "$WORK/benchmark-report.signature")" \
  -F "payload_digest=$(cat "$WORK/benchmark-report.digest")" \
  -F "challenge_nonce=$NONCE" \
  -F "client_version=gate-0.1.0" \
  -F "model_release_id=model-qwq-32b" \
  -F "quantization_profile_id=q-gguf-q4-k-m" \
  -F "inference_runtime_id=llama-cpp" \
  -F "artifact_0=@$WORK/benchmark-report.artifact_0.txt")
[ "$UPLOAD" = "202" ] && pass "POST /v1/submissions -> 202" || { fail "POST /v1/submissions -> $UPLOAD ($(cat "$WORK/upload.json"))"; }
RUN_ID=$(uv run python -c "import json; print(json.load(open('$WORK/upload.json'))['run_id'])" 2>/dev/null)

SEEN=1
for _ in $(seq 1 40); do
  if curl -sf "http://localhost:$API_PORT/v1/leaderboard" | uv run python -c "
import json, sys
body = json.load(sys.stdin)
ids = [run['run_id'] for run in body.get('runs', [])]
raise SystemExit(0 if '$RUN_ID' in ids else 1)" 2>/dev/null; then SEEN=0; break; fi
  sleep 1
done
check_exit "$SEEN" "GET /v1/leaderboard contains run $RUN_ID as validated"

echo "=== 7. Exit criteria ==="
uv run python -m tests.regression.vram_error_harness | tail -3
check_exit "${PIPESTATUS[0]}" "VRAM prediction P50 < 10%"
echo "NOTE  10-machine criterion: re-run step 4 on each internal machine:"
echo "      cd cli/benchmark-probe && cargo run -- --runtime mock --output benchmark-report.json"

echo
if [ "$FAILED" -eq 0 ]; then echo "GATE RESULT: PASS"; else echo "GATE RESULT: FAIL"; fi
exit "$FAILED"
