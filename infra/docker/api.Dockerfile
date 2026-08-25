# Single image for the two Python services (public-api + intake-worker).
# Both are thin layers over the monorepo; the command differs per service.
FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependency layer first (cache-friendly)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

# Application code (packages first: they change less than apps)
COPY packages/ packages/
COPY apps/public-api/ apps/public-api/
COPY apps/intake-worker/ apps/intake-worker/
# migrations + seed are applied from inside the container on first boot
COPY infra/migrations/ infra/migrations/
COPY infra/seed/ infra/seed/
COPY infra/scripts/ infra/scripts/

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONPATH="/app/packages/domain-schema/src:/app/packages/roofline-kernel/src:/app/packages/runtime-probes/src:/app/packages/recommendation-engine/src:/app/packages/fake-adapters/src"

WORKDIR /app/apps/public-api
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/v1/submissions/nonce', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
