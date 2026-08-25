.PHONY: test migrate seed check-ports infra-up gate prod-up prod-migrate backup-db

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
