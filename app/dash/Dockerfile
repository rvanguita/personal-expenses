# Dash app (read-only dashboard). Build context is the repository root (see docker-compose.yml):
#   docker build -f app/dash/Dockerfile .
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    DASH_PORT=8050

# curl for the healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Dependencies first (cached layer)
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

# Shared backend, project data and this app only
COPY src/ ./src/
COPY data/ ./data/
COPY template/ ./template/
COPY app/__init__.py ./app/__init__.py
COPY app/dash/ ./app/dash/
RUN uv sync --frozen --no-dev

WORKDIR /app/app/dash

EXPOSE 8050

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl --fail http://localhost:8050/ || exit 1

# `--no-sync`: the venv was fully synced at build time.
CMD ["uv", "run", "--no-sync", "python", "main.py"]
