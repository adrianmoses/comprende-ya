# Stage 1: Build Python deps
FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    software-properties-common \
    && add-apt-repository -y ppa:deadsnakes/ppa \
    && apt-get update && apt-get install -y --no-install-recommends \
    python3.12 python3.12-venv python3.12-dev curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /build

# Copy workspace pyproject files for dependency resolution
COPY pyproject.toml /build/pyproject.toml
COPY voice-agent/pyproject.toml /build/voice-agent/pyproject.toml
# Stub for workspace resolution (mcp package is a sibling workspace member)
COPY comprende-ya-mcp/pyproject.toml /build/comprende-ya-mcp/pyproject.toml
RUN mkdir -p /build/voice-agent/voice_agent /build/comprende-ya-mcp/mcp_server \
    && touch /build/voice-agent/voice_agent/__init__.py /build/comprende-ya-mcp/mcp_server/__init__.py

# Install deps — use UV_PROJECT_ENVIRONMENT so uv sync installs into /app/.venv
# (final runtime path) instead of /build/.venv, keeping shebangs correct after COPY.
ENV UV_PROJECT_ENVIRONMENT=/app/.venv
RUN uv venv /app/.venv --python python3.12 \
    && uv sync --package voice-agent --no-dev

# Stage 2: Runtime
FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    software-properties-common \
    && add-apt-repository -y ppa:deadsnakes/ppa \
    && apt-get update && apt-get install -y --no-install-recommends \
    python3.12 libsndfile1 curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy venv from builder (built at /app/.venv so shebangs match)
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
ENV VIRTUAL_ENV="/app/.venv"

# CUDA libs are already on LD_LIBRARY_PATH in the nvidia base image,
# so _ensure_nvidia_lib_path() becomes a no-op. Set explicitly for ctranslate2.
ENV LD_LIBRARY_PATH="/app/.venv/lib/python3.12/site-packages/nvidia/cublas/lib:/app/.venv/lib/python3.12/site-packages/nvidia/cudnn/lib:${LD_LIBRARY_PATH}"

WORKDIR /app/voice-agent

COPY voice-agent/ /app/voice-agent/

ENV PIPER_MODEL_PATH="/models/piper/es_ES-carlfm-x_low.onnx"
ENV HF_HOME="/models/whisper"

EXPOSE 8765

CMD ["python", "voice_agent_pipecat.py"]
