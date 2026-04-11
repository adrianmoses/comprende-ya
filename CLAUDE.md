# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ComprendeYa API — a FastAPI backend for generating Spanish language comprehension exercises from YouTube videos. It downloads audio, transcribes it via OpenAI Whisper, generates comprehension questions with Claude, and creates fill-in-the-blank exercises using spaCy NLP.

## Commands

```bash
# Install dependencies
uv sync --frozen --no-cache

# Run development server
uv run fastapi run src/main.py --host 0.0.0.0 --port 8000

# Database migrations
alembic upgrade head                              # Apply all migrations
alembic revision --autogenerate -m "description"  # Generate new migration
alembic downgrade -1                              # Rollback last migration

# Docker
docker build -t comprende-ya .
docker run -p 8000:8000 comprende-ya
```

No test suite or linter is currently configured.

## Environment

Requires a `.env` file (see `.env.example`):
- `ANTHROPIC_API_KEY` — Claude API for question generation and dialect classification
- `OPENAI_API_KEY` — Whisper API for audio transcription
- `YOUTUBE_API_KEY` — YouTube Data API for search and metadata
- `DATABASE_URL` — PostgreSQL connection string (default: `postgresql://postgres:postgres@localhost:5432/comprende_ya`)
- `DATABASE_ECHO` — optional, enables SQL query logging

System dependency: `ffmpeg` (required by yt-dlp for audio extraction).

## Architecture

### Layered structure under `src/`

- **`api/routes/`** — FastAPI endpoint definitions. `videos.py` is the main router.
- **`services/`** — Business logic and external API integrations (YouTube download, Whisper transcription, Claude question generation, spaCy exercise generation, dialect classification).
- **`repositories/`** — Database access layer using SQLModel. Each repository handles CRUD for a specific model.
- **`models/database.py`** — SQLModel table definitions (videos, questions, video_segments, answer_progress, frase_exercise).
- **`models/schemas.py`** — Pydantic request/response schemas.
- **`flows/video_processing.py`** — Prefect workflow that orchestrates the full video processing pipeline as background tasks.
- **`config.py`** — Settings loaded from environment via python-dotenv.
- **`db.py`** — Database engine and session management.

### Video processing pipeline

`POST /api/videos/process-async` triggers a Prefect flow (`process_video_flow`) that runs in a background task:

1. Download audio via yt-dlp
2. Transcribe with OpenAI Whisper (verbose_json, segment granularity, language=es)
3. Generate timestamped comprehension questions with Claude (3 types: colloquial expressions 40%, comprehension 30%, vocabulary 30%)
4. Save video + questions to database
5. Extract transcript segments → VideoSegment records
6. Generate fill-in-the-blank exercises via spaCy (`es_dep_news_trf` model) with difficulty levels (facil/medio/dificil)
7. Save exercises, clean up temp files

Poll `GET /api/videos/status/{flow_run_id}` for progress.

### Key patterns

- **Repository pattern** for all database access
- **Service singletons** instantiated at module level (e.g., `youtube_service`, `question_service`)
- **Dependency injection** via FastAPI's `Depends()` for DB sessions
- **JSON strings** stored in DB columns for complex data (answers, hints, transcript segments)
- AI models used: `claude-4-sonnet-20250514` for text generation, OpenAI Whisper for transcription
- CORS allows `localhost:3000` (frontend dev)
- Video duration limit: 1 hour
