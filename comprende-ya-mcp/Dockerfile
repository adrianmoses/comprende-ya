# Stage 1: Build Python deps
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /build

# Copy workspace pyproject files for dependency resolution
COPY pyproject.toml /build/pyproject.toml
COPY comprende-ya-mcp/pyproject.toml /build/comprende-ya-mcp/pyproject.toml
# Stub for workspace resolution (voice-agent is a sibling workspace member)
COPY voice-agent/pyproject.toml /build/voice-agent/pyproject.toml
RUN mkdir -p /build/voice-agent/voice_agent /build/comprende-ya-mcp/mcp_server \
    && touch /build/voice-agent/voice_agent/__init__.py /build/comprende-ya-mcp/mcp_server/__init__.py

# Install deps — use UV_PROJECT_ENVIRONMENT so uv sync installs into /app/.venv
# (final runtime path) instead of /build/.venv, keeping shebangs correct after COPY.
ENV UV_PROJECT_ENVIRONMENT=/app/.venv
RUN uv venv /app/.venv --python python3.12 \
    && uv sync --package comprende-ya-mcp --no-dev

# Stage 2: Runtime
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY comprende-ya-mcp/ /app/comprende-ya-mcp/
COPY concept_graph.json /app/concept_graph.json

ENV PATH="/app/.venv/bin:$PATH"
ENV VIRTUAL_ENV="/app/.venv"

WORKDIR /app/comprende-ya-mcp

EXPOSE 8001

HEALTHCHECK --interval=10s --timeout=5s --retries=5 --start-period=10s \
    CMD curl -sf http://localhost:8001/health || exit 1

CMD ["python", "-m", "mcp_server.server"]
