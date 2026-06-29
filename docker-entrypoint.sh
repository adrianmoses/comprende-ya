#!/usr/bin/env bash
# Entrypoint del contenedor de la API (033 — deployment readiness).
# Aplica las migraciones y luego arranca el servidor. Idempotente: `alembic
# upgrade head` no hace nada si la base ya está al día, así que es seguro en
# cada arranque/reinicio.
set -euo pipefail

echo "[entrypoint] alembic upgrade head"
uv run alembic upgrade head

echo "[entrypoint] starting FastAPI on 0.0.0.0:8000"
exec uv run fastapi run src/main.py --host 0.0.0.0 --port 8000
