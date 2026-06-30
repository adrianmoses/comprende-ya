FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Install system dependencies (ffmpeg for yt-dlp)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-cache

# Copy application code
COPY . .

# Create runtime directories. `recordings/` is mounted as a persistent volume in
# docker-compose (033); `temp/` holds transient audio during processing.
RUN mkdir -p temp recordings && chmod +x docker-entrypoint.sh

# Expose port
EXPOSE 8000

# Migrate-then-serve (033): the entrypoint runs `alembic upgrade head` before
# starting the server, so a fresh database comes up fully migrated.
ENTRYPOINT ["./docker-entrypoint.sh"]
