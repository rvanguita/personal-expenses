# Use official uv image with Python 3.13 slim
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS base

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    STREAMLIT_SERVER_PORT=8503 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Copy configuration and dependency specifications
COPY pyproject.toml uv.lock README.md ./

# Install dependencies using uv sync (cached layer)
RUN uv sync --frozen --no-dev --no-install-project

# Copy source code and data assets
COPY src/ ./src/
COPY data/ ./data/
COPY template/ ./template/
COPY .streamlit/ ./.streamlit/
COPY main.py ./

# Install project itself
RUN uv sync --frozen --no-dev

# Streamlit application port
EXPOSE 8503

# Healthcheck for the Streamlit command
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl --fail http://localhost:8503/_stcore/health || exit 1

# Command to launch the Streamlit application
CMD ["uv", "run", "streamlit", "run", "main.py", "--server.port=8503", "--server.address=0.0.0.0"]
