# Streamlit app. Build context is the repository root (see docker-compose.yml):
#   docker build -f app/streamlit/Dockerfile .
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    STREAMLIT_SERVER_PORT=8503 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# curl for the healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Dependencies first (cached layer). The workspace lock needs every member's pyproject.toml,
# but only this app's dependency tree is installed (`--package`).
COPY pyproject.toml uv.lock README.md ./
COPY app/streamlit/pyproject.toml ./app/streamlit/pyproject.toml
COPY app/dash/pyproject.toml ./app/dash/pyproject.toml
RUN uv sync --frozen --no-dev --package expenses-streamlit --no-install-workspace

# Shared backend (package `expenses`), project data and this app only
COPY src/ ./src/
COPY data/ ./data/
COPY template/ ./template/
COPY app/streamlit/ ./app/streamlit/
RUN uv sync --frozen --no-dev --package expenses-streamlit

# Streamlit reads .streamlit/config.toml from the working directory, i.e. this app's folder.
WORKDIR /app/app/streamlit

EXPOSE 8503

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl --fail http://localhost:8503/_stcore/health || exit 1

# The venv was fully synced at build time, so `--no-sync` stops `uv run` from re-syncing (and
# installing the dev group) every time the container starts.
CMD ["uv", "run", "--no-sync", "streamlit", "run", "main.py", "--server.port=8503", "--server.address=0.0.0.0"]
