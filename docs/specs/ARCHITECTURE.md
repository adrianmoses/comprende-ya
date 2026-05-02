# Architecture

<!-- status: inferred -->
| Field | Value |
|---|---|
| status | approved |
| created | 2026-05-02 |
| inferred-from | `src/main.py`, `src/config.py`, `src/db.py`, `src/api/routes/videos.py`, `src/flows/video_processing.py`, `src/services/*`, `src/repositories/*`, `src/models/database.py`, `src/models/schemas.py`, `alembic/versions/*`, `Dockerfile`, `pyproject.toml`, `docs/artefacts/` |

## System Overview

ComprendeYa today is a single FastAPI process that exposes one router (`/api/videos`) and runs a Prefect flow inline as a FastAPI `BackgroundTask` to process YouTube videos. Persistence is PostgreSQL via SQLModel; schema is owned by Alembic. There is **no frontend yet** — CORS is configured for `http://localhost:3000`, signaling the intended frontend origin.

```
┌──────────────────────────────────────────────────────────────────────┐
│                  Planned Frontend (Vite Nitro React)                 │
│                       http://localhost:3000                          │
│   Inicio  ·  Escuchando (Phrase Autopsy)  ·  Mis frases              │
└──────────────────────────────────────────────────────────────────────┘
                               │  HTTP (CORS)
┌──────────────────────────────▼───────────────────────────────────────┐
│                   FastAPI app  (src/main.py)                         │
│   /api/videos  ·  /health  ·  /                                      │
│                                                                      │
│   ┌──────────── api/routes/videos.py ────────────┐                   │
│   │  search · process-async · status · video CRUD │                  │
│   │  segments · progress · classify              │                   │
│   └────────┬─────────────────┬─────────┬─────────┘                   │
│            │                 │         │                             │
│   ┌────────▼─────┐   ┌───────▼────┐   ┌▼────────────┐                │
│   │  services/   │   │  flows/    │   │ repositories │               │
│   │              │   │            │   │              │               │
│   │ youtube      │   │ Prefect    │   │ Video        │               │
│   │ youtube_     │   │ flow:      │   │ Segments     │               │
│   │  search      │──▶│ Process    │──▶│ Exercise     │               │
│   │ youtube_     │   │ Video      │   │ Progress     │               │
│   │  transcript  │   │            │   │ Classifier   │               │
│   │ transcription│   │            │   └──────┬───────┘               │
│   │ questions    │   │            │          │                       │
│   │ frase_       │   │            │          │                       │
│   │  exercise_   │   │            │          │                       │
│   │  generator   │   │            │          │                       │
│   │ dialect_     │   │            │          │                       │
│   │  classifier  │   │            │          │                       │
│   └──────────────┘   └────────────┘          ▼                       │
│                                       ┌──────────────┐               │
│                                       │ PostgreSQL   │               │
│                                       │ (SQLModel +  │               │
│                                       │  Alembic)    │               │
│                                       └──────────────┘               │
└──────────────────────────────────────────────────────────────────────┘
            │                 │              │            │
            ▼                 ▼              ▼            ▼
       YouTube Data     YouTube Trans-   OpenAI       Anthropic
       API v3           cript API +      Whisper      Claude
       (search)         yt-dlp (audio)   (verbose)    (Q-gen + dialect)
```

## Component Map

Layered monolith under `src/`:

| Layer | Path | Role |
|---|---|---|
| **Entry / app config** | `src/main.py`, `src/config.py` | FastAPI factory, CORS, env loading, eager API-key validation |
| **API routes** | `src/api/routes/videos.py` | Sole router; mounted at `/api/videos` |
| **Pydantic schemas** | `src/models/schemas.py` | `VideoRequest`, `VideoResponse`, `TimestampedQuestion`, `FillInBlankExercise`, `DetailedTranscript`, `TranscriptSegment` |
| **DB models** | `src/models/database.py` | SQLModel tables: `Video`, `Question`, `VideoSegment`, `AnswerProgress`, `FraseExercise` |
| **DB engine / session** | `src/db.py` | `engine`, `get_session` (FastAPI dep), `get_db_session` (context manager for Prefect tasks) |
| **Migrations** | `alembic/versions/*` | 6 migrations — initial videos+questions, h5p (added then removed), video_segments, frase_exercise, answer_progress |
| **Services (external integrations)** | `src/services/*` | `youtube` (yt-dlp), `youtube_search` (Data API), `youtube_transcript` (transcript-api), `transcription` (Whisper), `questions` (Claude), `frase_exercise_generator` (spaCy), `dialect_classifier` (Claude) |
| **Repositories (DB access)** | `src/repositories/*` | `video_repository`, `segments_repository`, `exercise_repository`, `progress_repository`, `classifier_repository` |
| **Background pipeline** | `src/flows/video_processing.py` | Prefect `@flow` orchestrating download → transcribe → generate → save → segment → exercises → cleanup |
| **Container** | `Dockerfile` | `astral-sh/uv` Python 3.12 base, ffmpeg, port 8000 |

**Service singleton pattern.** Every service module instantiates a singleton at module level (`youtube_service`, `question_service`, `transcription_service`, `dialect_classifier`, `youtube_search`, `youtube_transcript_service`). `FraseExerciseGeneratorService` is the exception — it's instantiated per-flow because its difficulty is constructor-time configuration.

**Repository pattern, per-session.** Each repository takes a `Session` in `__init__` and exposes CRUD-ish methods (`create`, `get_by_youtube_id`, `list`, `to_response`). `SegmentsRepository` doubles as a derivation step: if a video has `full_transcript_data` JSON but no `VideoSegment` rows, calling `extract_and_save_segments` materialises them.

## Data Flow

### Implemented: video processing pipeline

1. **`POST /api/videos/process-async`** (`videos.py:100`)
   - Extracts YouTube ID via regex from the URL
   - Dedup check by `youtube_id` (skip unless `force=true`); if existing, return cached payload immediately with `status: "EXISTS"`
   - Generates a `flow_run_id` UUID, registers `{status: "PENDING"}` in the in-memory `flow_runs` dict
   - Queues `run_flow_background` as a `BackgroundTask`, returns `202`-style response with `flow_run_id`

2. **`run_flow_background`** (`videos.py:31`)
   - Sets state to `RUNNING`, calls `process_video_flow(video_url, force)` directly
   - On exception, records `FAILED` + error string

3. **`process_video_flow`** (`flows/video_processing.py:133`) — Prefect flow with `@task`-wrapped steps:
   1. `download_audio` — yt-dlp pulls bestaudio, FFmpeg extracts MP3 at 64 kbps to `temp/{id}.mp3`. Hard-fails if `duration > MAX_VIDEO_DURATION` (3600 s). Returns `(audio_path, metadata)`.
   2. `transcribe_with_timestamps` — OpenAI Whisper `whisper-1`, `language="es"`, `response_format="verbose_json"`, `timestamp_granularities=["segment"]`. Returns `DetailedTranscript(full_text, segments[], duration)`.
   3. `generate_timestamped_questions` — splits the video into N=5 equal time sections, samples segments per section, prompts Claude for one MCQ per section (40% colloquial / 30% comprehension / 30% vocabulary), parses JSON from the response, sorts by timestamp.
   4. `save_to_database` — uses `get_db_session` context manager. If exists+force, replaces questions; if exists, returns existing ID; else creates `Video` + `Question` rows via `VideoRepository`.
   5. `save_video_segments` — `SegmentsRepository.extract_and_save_segments` reads stored `full_transcript_data` JSON, writes `VideoSegment` rows.
   6. `generate_exercises_task` — instantiates `FraseExerciseGeneratorService(difficulty="medio")`, samples ~10 % of segments, runs each through spaCy `es_dep_news_trf`, picks 2-4 blank candidates by POS-priority, returns dicts.
   7. `save_exercises_task` — `ExerciseRepository.create_exercises`.
   8. `cleanup` — removes the temp MP3.

4. **Polling.** Frontend polls `GET /api/videos/status/{flow_run_id}` until `COMPLETED` / `FAILED`, then fetches `GET /api/videos/{video_id}` for the full payload.

### Implemented: non-pipeline reads

- `GET /api/videos/{video_id}` returns video + all questions (answers/explanation parsed from JSON) + all fill-in-blank exercises.
- `GET /api/videos/{video_id}/segments` returns ordered `VideoSegment` rows; lazy-extracts from `full_transcript_data` if missing.
- `POST/GET/DELETE /api/videos/{video_id}/progress` — single-user MCQ answer tracking, keyed `(video_id, question_id)`.
- `GET /api/videos/{video_id}/classify` — runs Claude over stored full transcript and returns `{dialect, confidence, signals[]}`.

### Planned: frontend data flow (per design)

The frontend will be an SPA hitting the same `/api/videos` surface. Three screens map onto existing or planned endpoints:

| Screen | Reads | Writes | Notes |
|---|---|---|---|
| **Inicio** (Home) | `GET /api/videos/` (library), per-video progress aggregates | — | KPIs (week minutes / streak / comprehension %) need a new aggregation endpoint or a `users` table. |
| **Escuchando** (Listen) | `GET /api/videos/{id}`, `GET /api/videos/{id}/segments`, **NEW** Phrase Autopsy fetch | `POST /api/videos/{id}/progress` per MCQ, **NEW** save-phrase / unsave-phrase | Tappable token-level transcript needs token annotations not currently in `VideoSegment.transcript_text`. |
| **Mis frases** (Chunks) | **NEW** `GET /api/chunks` | **NEW** `POST /api/chunks/{id}/recording` | Whole feature is unimplemented. |


frontend will be a vite SPA project with a nitro web server to support running standalone 

## External Dependencies

| Dependency | Used by | Failure mode |
|---|---|---|
| **YouTube Data API v3** | `services/youtube_search.py` | `quotaExceeded` returns 403 from Google; not currently caught |
| **YouTube Transcript API** (community lib `youtube-transcript-api`) | `services/youtube_transcript.py` | `TranscriptsDisabled` / `NoTranscriptFound` / `VideoUnavailable` caught and returned as `None` |
| **yt-dlp + ffmpeg** | `services/youtube.py` | yt-dlp is a hot dependency — bot-detection / format changes break it; pinned to `>=2025.10.22` |
| **OpenAI Whisper API** | `services/transcription.py` | No retry, no chunking — large audio just gets sent (Whisper API has a 25 MB limit; 64 kbps mono should fit ~50 min) |
| **Anthropic Claude API** | `services/questions.py`, `services/dialect_classifier.py`, `repositories/classifier_repository.py` | Hard-coded model IDs (`claude-4-sonnet-20250514`, `claude-sonnet-4-20250514`) — these are stale; real current models are Opus 4.7 / Sonnet 4.6 / Haiku 4.5 |
| **spaCy `es_dep_news_trf`** | `services/frase_exercise_generator.py` | Loads at service construction with `spacy.prefer_gpu()` — will silently fall back to CPU if no CUDA. Model not auto-downloaded by `uv sync`; needs `python -m spacy download es_dep_news_trf` separately. |
| **PostgreSQL** | `db.py` via SQLModel | `pool_pre_ping=True` covers connection drops; no read replicas, no migrations on startup |
| **Prefect 3.x** | `flows/video_processing.py` | Runs in-process; `flow_runs` dict for status — restart loses all in-flight state |

## Key Constraints

- **Python `>=3.12`** (set in `pyproject.toml`).
- **Hard 1-hour cap on input video** (`config.py:27`, enforced in `youtube.py:33`).
- **Eager API-key validation at import** (`config.py:18-23` raises if any of `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `YOUTUBE_API_KEY` is missing). Means tests / local dev that wants to import the package must have all three set.
- **CORS is single-origin** — `http://localhost:3000` only. Will need to be parameterised for staging/prod.
- **Single FastAPI process** owns the queue. Background flow is `BackgroundTasks`, not a worker pool — concurrent uploads will run on the FastAPI event loop and contend for the spaCy GPU model and the API rate limits.
- **Flow status is in-memory** (`flow_runs` dict, `videos.py:29`). Restart drops every entry, the dict grows unbounded for the lifetime of the process, and a multi-worker deploy would split state across workers. The flow itself completes (DB rows land correctly); the status surface is what's unfinished. Planned fix: persist a `processing_jobs` row per `flow_run_id` and read status from the DB. See ROADMAP item 012.
- **Default exercise difficulty is hard-coded** to `"medio"` in `flows/video_processing.py:173`. No UI control.
- **MCQs are always exactly 5** (default `num_questions=5` in `services/questions.py:91`), distributed via even time-section split.
- **Fill-in-blank sample rate is 10 %** of segments (`frase_exercise_generator.py:157`).
- **`temp/` directory exists at repo root** — `youtube.py` writes audio there; `cleanup` removes individual files but never the dir.
- **Spanish-only** — Whisper called with `language="es"`; YouTube search forces `relevanceLanguage='es'`; transcript API tries `['es', 'es-ES', 'es-MX', 'es-419']`.
