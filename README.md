# ComprendeYa

A FastAPI backend that turns YouTube videos into Spanish-language listening comprehension exercises. The pipeline downloads audio with `yt-dlp`, transcribes it with OpenAI Whisper, generates timestamped comprehension questions with Claude, and produces fill-in-the-blank exercises with spaCy.

The desktop frontend lives in [`webapp/`](webapp/README.md) (TanStack Start + React 19).

## Repo layout

```
src/
  api/routes/      FastAPI endpoints (videos.py is the main router)
  services/        External API integrations: YouTube, Whisper, Claude, spaCy, dialect classifier
  repositories/    SQLModel-based DB access layer
  models/          SQLModel tables (database.py) + Pydantic schemas (schemas.py)
  flows/           Prefect workflow that orchestrates the video processing pipeline
  config.py        Settings loaded from .env via python-dotenv
  db.py            SQLAlchemy/SQLModel engine + session
  main.py          FastAPI app entrypoint
alembic/           DB migrations
webapp/            TanStack Start frontend (own README)
docs/              Specs and design artefacts
tests/             Pytest suite (currently minimal)
```

### Pipeline at a glance

`POST /api/videos/process-async` kicks off a Prefect flow that:

1. Downloads audio with `yt-dlp` (requires `ffmpeg`)
2. Transcribes via Whisper (`verbose_json`, segment granularity, `language=es`)
3. Generates comprehension questions with Claude (colloquial 40% / comprehension 30% / vocabulary 30%)
4. Persists video + questions, then expands transcript into `VideoSegment` rows
5. Generates fill-in-the-blank exercises with spaCy (`es_dep_news_trf`) at three difficulty levels
6. Cleans up temp files

Poll `GET /api/videos/status/{flow_run_id}` for progress.

## Prerequisites

- Python **3.12+**
- [`uv`](https://github.com/astral-sh/uv) for dependency management
- PostgreSQL (local or remote)
- `ffmpeg` (used by `yt-dlp` for audio extraction)
  - macOS: `brew install ffmpeg`
  - Debian/Ubuntu: `apt-get install ffmpeg`
- API keys for Anthropic, OpenAI, and the YouTube Data API

## Run locally

### 1. Install dependencies

```bash
uv sync --frozen --no-cache
```

This also installs the spaCy Spanish transformer model declared in the lockfile. If `es_dep_news_trf` is missing at runtime, install it manually:

```bash
uv run python -m spacy download es_dep_news_trf
```

### 2. Configure environment

Copy the example file and fill in your keys:

```bash
cp .env.example .env
```

Required variables (see `src/config.py`):

| Variable | Purpose |
| --- | --- |
| `ANTHROPIC_API_KEY` | Claude — question generation, dialect classification |
| `OPENAI_API_KEY` | Whisper — audio transcription |
| `YOUTUBE_API_KEY` | YouTube Data API — search and metadata |
| `DATABASE_URL` | Postgres connection string (default `postgresql://postgres:postgres@localhost:5432/comprende_ya`) |
| `DATABASE_ECHO` | Optional — set `true` to log SQL queries |

### 3. Start Postgres and create the database

If you don't already have a Postgres instance, the simplest path is Docker:

```bash
docker run --name comprende-ya-pg \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=comprende_ya \
  -p 5432:5432 \
  -d postgres:16
```

Or with a local install:

```bash
createdb comprende_ya
```

### 4. Apply database migrations

Migrations are managed with Alembic and live in `alembic/versions/`.

```bash
# Apply every migration up to the latest
uv run alembic upgrade head

# Generate a new migration from model changes
uv run alembic revision --autogenerate -m "describe your change"

# Roll back the most recent migration
uv run alembic downgrade -1

# Inspect history / current revision
uv run alembic history
uv run alembic current
```

Re-run `alembic upgrade head` after pulling changes that touch `src/models/database.py` or add a new file to `alembic/versions/`.

### 5. Start the API

```bash
uv run fastapi run src/main.py --host 0.0.0.0 --port 8000
```

For autoreload during development:

```bash
uv run fastapi dev src/main.py --port 8000
```

The API is now available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

### 6. (Optional) Start the frontend

```bash
cd webapp
pnpm install
pnpm dev   # http://localhost:3000
```

CORS on the backend is preconfigured for `http://localhost:3000`.

## Docker

```bash
docker build -t comprende-ya .
docker run --env-file .env -p 8000:8000 comprende-ya
```

The image bundles `ffmpeg` and runs `fastapi run src/main.py` on port 8000. Migrations are not applied automatically — run `alembic upgrade head` against your target database before (or as part of) deployment.

## Useful endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/videos/search` | YouTube search |
| `POST` | `/api/videos/process-async` | Kick off the processing pipeline |
| `GET` | `/api/videos/status/{flow_run_id}` | Poll Prefect flow status |
| `GET` | `/api/videos/{video_id}` | Fetch a processed video + questions |
| `GET` | `/api/videos/{video_id}/segments` | Transcript segments |
| `POST`/`GET`/`DELETE` | `/api/videos/{video_id}/progress` | Per-user answer progress |

See `src/api/routes/videos.py` for the full surface.

## Tests and tooling

```bash
uv run pytest         # test suite (currently minimal)
uv run ruff check .   # lint
uv run ruff format .  # format
```
