# Frontend production image (033 — deployment readiness).
# TanStack Start (Vite + React 19) + Nitro. `vite build` emits a self-listening
# Nitro node-server at .output/server/index.mjs.
FROM node:22-bookworm-slim

# pnpm via corepack (matches the repo's package manager).
RUN corepack enable

WORKDIR /app

# Install deps first for layer caching.
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# VITE_API_BASE_URL is BUILD-TIME: Vite inlines import.meta.env at build (see
# src/lib/api.ts). It must be the PUBLIC, browser-reachable origin of the API —
# NOT the internal compose service name (http://api:8000). Passed as a build arg
# from docker-compose.
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

# Copy source and build (Nitro output → .output/).
COPY . .
RUN pnpm build

EXPOSE 3000

# Run the Nitro node-server (honors PORT/NITRO_PORT, default 3000).
CMD ["node", ".output/server/index.mjs"]
