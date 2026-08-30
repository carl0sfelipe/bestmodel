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

echo "=== 6b. Video leg (mock ComfyUI; no execute, fixture NDJSON) ==="
VALIDATED_BEFORE=$(pg "SELECT count(*) FROM benchmark_run WHERE status='validated';")
uv run python - "$BENCHMARK_PROBE_KEY_PATH" "$WORK" <<'EOF'
import hashlib, json, sys, time, uuid
from cryptography.hazmat.primitives.serialization import load_pem_private_key

key_path, work = sys.argv[1], sys.argv[2]
# Per-run fingerprint so repeated gate runs never trip the 5-dim dedupe.
fingerprint = "sha256:" + hashlib.sha256(f"gate-video-{time.time_ns()}".encode()).hexdigest()
seconds_per_clip = 12.5
it_per_s = 20 / seconds_per_clip      # steps / clip time
frames_per_s = 81 / seconds_per_clip  # frames / clip time
evidence = (
    "metric seconds_per_clip 12.500\n"
    "metric it_per_s 1.600\n"
    "metric frames_per_s 6.480\n"
    "metric peak_vram_mib 0\n"
)
report = {
    "schema_version": "0.9.0",
    "run_id": str(uuid.uuid4()),
    "runtime": "comfyui",
    "runtime_version": "0.3.48",
    "hardware_fingerprint": fingerprint,
    "scenario": {
        "scenario_kind": "video", "width": 1280, "height": 720,
        "frames": 81, "steps": 20, "cfg": 3.5, "shift": 5.0, "seed": 42,
    },
    "metrics": {
        "ttft_ms": 0.0, "prefill_tok_s": 0.0, "decode_tok_s": 0.0,
        "peak_vram_mib": 0, "power_watt_avg": 0.0,
        "seconds_per_clip": seconds_per_clip, "it_per_s": it_per_s,
        "frames_per_s": frames_per_s,
    },
    "artifacts": [{"artifact_kind": "runtime_stdout", "sha256": hashlib.sha256(evidence.encode()).hexdigest()}],
    "recipe_id": "wan22-flf2v-720p-81f-v1",
}
canonical = json.dumps(report, sort_keys=True, separators=(",", ":"))
digest = "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()
key = load_pem_private_key(open(key_path, "rb").read(), password=None)
signature = key.sign(digest.encode()).hex()
open(f"{work}/video-report.json", "w").write(canonical)
open(f"{work}/video-evidence.ndjson", "w").write(evidence)
open(f"{work}/video.digest", "w").write(digest)
open(f"{work}/video.sig", "w").write(signature)
print(f"video fixture ready (fingerprint {fingerprint[:16]}...)")
EOF
check_exit "$?" "video fixture built + signed with the gate key"

VNONCE=$(curl -sf "http://localhost:$API_PORT/v1/submissions/nonce" | uv run python -c "import json,sys; print(json.load(sys.stdin)['challenge_nonce'])")
VUPLOAD=$(curl -s -o "$WORK/video-upload.json" -w "%{http_code}" -X POST "http://localhost:$API_PORT/v1/submissions" \
  -F "report=<$WORK/video-report.json" \
  -F "signature=$(cat "$WORK/video.sig")" \
  -F "payload_digest=$(cat "$WORK/video.digest")" \
  -F "challenge_nonce=$VNONCE" \
  -F "client_version=gate-video-0.1.0" \
  -F "model_release_id=model-wan22-i2v-flf2v-14b" \
  -F "quantization_profile_id=q-fp16" \
  -F "inference_runtime_id=comfyui" \
  -F "recipe_id=wan22-flf2v-720p-81f-v1" \
  -F "artifact_0=@$WORK/video-evidence.ndjson")
echo "      POST /v1/submissions (video mock) -> $VUPLOAD"
[ "$VUPLOAD" = "202" ] && pass "POST /v1/submissions (video mock) -> 202" || { fail "POST /v1/submissions (video mock) -> $VUPLOAD ($(cat "$WORK/video-upload.json"))"; }
VRUN_ID=$(uv run python -c "import json; print(json.load(open('$WORK/video-upload.json'))['run_id'])" 2>/dev/null)

VVALID=1
for _ in $(seq 1 40); do
  VSTATUS=$(pg "SELECT status FROM benchmark_run WHERE id = '$VRUN_ID';")
  [ "$VSTATUS" = "validated" ] && VVALID=0 && break
  sleep 1
done
check_exit "$VVALID" "video run $VRUN_ID reaches validated in Postgres"

VALIDATED_AFTER=$(pg "SELECT count(*) FROM benchmark_run WHERE status='validated';")
[ "${VALIDATED_AFTER:-0}" -gt "${VALIDATED_BEFORE:-0}" ] && pass "leaderboard row count increased (${VALIDATED_BEFORE:-0} -> ${VALIDATED_AFTER:-0})" || fail "leaderboard row count did not increase (${VALIDATED_BEFORE:-0} -> ${VALIDATED_AFTER:-0})"

VSEEN=1
for _ in $(seq 1 20); do
  if curl -sf "http://localhost:$API_PORT/v1/leaderboard?model_release_id=model-wan22-i2v-flf2v-14b" | uv run python -c "
import json, sys
runs = json.load(sys.stdin).get('runs', [])
row = next((r for r in runs if r.get('run_id') == '$VRUN_ID'), None)
assert row is not None, 'video run missing from leaderboard'
assert row.get('source_class'), f'source_class missing/empty: {row.get(\"source_class\")!r}'
assert row.get('recipe_id') == 'wan22-flf2v-720p-81f-v1', f'wrong recipe_id: {row.get(\"recipe_id\")!r}'
assert row.get('seconds_per_clip') and abs(row['seconds_per_clip'] - 12.5) < 0.01, f'seconds_per_clip: {row.get(\"seconds_per_clip\")!r}'
assert row.get('frames_per_s') and abs(row['frames_per_s'] - 6.48) < 0.01, f'frames_per_s: {row.get(\"frames_per_s\")!r}'
" 2>/dev/null; then VSEEN=0; break; fi
  sleep 1
done
check_exit "$VSEEN" "leaderboard video row carries source_class + recipe + scalars"

uv run pytest tests/test_session_video_roundtrip.py -q >/dev/null 2>&1
check_exit "$?" "S25a-rt round-trip both backends (Postgres leg via DATABASE_URL)"

# D4: presence-only enforcement — content freshness cannot be honestly
# mechanized, presence can. Every directory on the run-data path must carry
# an AGENTS.md with the two mandatory sections at the edit site.
D4_DIRS="packages/domain-schema packages/fake-adapters packages/roofline-kernel packages/recommendation-engine apps/public-api apps/intake-worker cli/benchmark-probe infra/migrations infra/seed"
D4_MISSING=0
for d in $D4_DIRS; do
  if [ ! -f "$d/AGENTS.md" ] || ! grep -q "## Change checklist" "$d/AGENTS.md"; then
    echo "  D4 GAP: $d/AGENTS.md missing or without '## Change checklist'"
    D4_MISSING=1
  fi
done
check_exit "$D4_MISSING" "D4: AGENTS.md with Change checklist present in all run-data dirs"

echo "=== 7. Exit criteria ==="
uv run python -m tests.regression.vram_error_harness | tail -3
check_exit "${PIPESTATUS[0]}" "VRAM prediction P50 < 10%"
echo "NOTE  10-machine criterion: re-run step 4 on each internal machine:"
echo "      cd cli/benchmark-probe && cargo run -- --runtime mock --output benchmark-report.json"

echo
if [ "$FAILED" -eq 0 ]; then echo "GATE RESULT: PASS"; else echo "GATE RESULT: FAIL"; fi
exit "$FAILED"
