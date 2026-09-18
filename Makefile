.PHONY: test migrate seed check-ports infra-up gate prod-up prod-migrate backup-db agent-smoke

test:
	uv run pytest -q

check-ports:
	uv run python infra/scripts/check_host_ports.py

infra-up: check-ports
	docker compose -f infra/docker/docker-compose.yml up -d

migrate:
	uv run python infra/scripts/migrate.py

seed: migrate
	uv run python infra/seed/load_seed.py

gate:
	bash infra/scripts/e2e_gate.sh

COMPOSE_PROD := docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env

prod-up:
	$(COMPOSE_PROD) --profile edge up -d --build

prod-migrate:
	$(COMPOSE_PROD) exec -T api sh -c "cd /app && uv run python infra/scripts/migrate.py && uv run python infra/seed/load_seed.py"

backup-db:
	deploy/scripts/backup-db.sh

# Rust-only cold-path smoke: exactly what a fresh AI-agent session runs
# (docs/agent-quickstart.md). No Docker, no uv, no keys, no network.
agent-smoke:
	cargo build --release -p canirunit -p benchmark-probe
	./target/release/benchmark-probe --runtime mock --model qwen3:8b
	./target/release/canirunit rigs --runs apps/web/data/derived/pool.json --filter rtx-3090
	./target/release/canirunit suggest --gpu rtx-3090-24gb --task decode_tok_s --runs apps/web/data/derived/pool.json > /dev/null
	@echo "suggest: ranking OK"
	./target/release/benchmark-probe lab --stub --trials 5 > /dev/null
	@echo "lab: TPE loop OK (SIM)"
	@echo "agent-smoke: ALL GREEN"
