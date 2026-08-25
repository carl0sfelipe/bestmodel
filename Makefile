.PHONY: test migrate seed check-ports infra-up gate

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
