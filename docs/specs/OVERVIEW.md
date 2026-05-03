# Overview

<!-- status: inferred -->
| Field | Value |
|---|---|
| status | approved |
| created | 2026-05-02 |
| inferred-from | `CLAUDE.md`, `pyproject.toml`, `src/main.py`, `src/api/routes/videos.py`, `src/flows/video_processing.py`, `src/services/*`, `src/models/database.py`, `src/models/schemas.py`, `alembic/versions/*`, `Dockerfile`, `docs/artefacts/` (design bundle) |

## Product Summary

ComprendeYa is a self-study tool for upper-intermediate (B2) Spanish learners who want to understand and produce *natural* spoken Spanish — not textbook Spanish. The user feeds in a YouTube video or podcast; the system transcribes it, generates timestamped multiple-choice comprehension questions, and produces fill-in-the-blank exercises that target real grammatical pressure points (subjunctive, prepositions `por`/`para`/`a`, object pronouns, connectors).

Today the repo is a **backend API only**. The product direction (per the design bundle in `docs/artefacts/`) is to add a calm, OS-native desktop web frontend with three primary screens — **Inicio** (library + KPIs), **Escuchando** (active-listening view with transcript, scrubber, MCQ side panel, and a *Phrase Autopsy* sentence inspector), and **Mis frases** (saved-phrase library with speaking prompts and self-recording).

## Target Consumer

A single self-directed B2 Spanish learner using the app on desktop web for focused study sessions. Inferred from:
- The design bundle's framing: "calm, self-study application for one person who wants to understand natural spanish"
- No multi-tenant / auth / user-accounts code in the backend
- CORS pinned to `localhost:3000` (single intended frontend origin)
- `MAX_VIDEO_DURATION = 3600` (one-hour cap matches a single study session)
- single-user only

## Job To Be Done

> "Help me understand what natural Spanish actually sounds like, and give me targeted practice on the bits I'd otherwise miss — colloquial expressions, idioms, tricky grammar — using real audio I'm interested in."

The implemented backend job: turn a YouTube URL into (1) a timestamped transcript, (2) ~5 comprehension MCQs distributed across the video, (3) a sample of fill-in-the-blank exercises, and (4) an optional dialect classification (España / México / Argentina / Caribe / Andino / Otro).

The **planned frontend job** (per design): render those artefacts in a focused listening UI, plus offer **Phrase Autopsy** (grammar breakdown → why-it-sounds-native, all in Spanish) and a **Chunk Library** of saved phrases with rotating speaking prompts and microphone recording.

## Non-Goals

Inferred from what is explicitly absent in the code:

- **No multi-user authentication / accounts.** No users table, no auth middleware, no session tokens.
- **No video hosting.** Audio is streamed via yt-dlp and discarded after transcription (`cleanup` task removes temp files).
- **No long-form videos.** Hard-capped at 1 hour (`config.py:27`).
- **No live transcription / real-time audio.** Pipeline is batch-oriented and runs after upload.
- **No content moderation, no copyright handling.** Trusts the user-provided URL.
- **No mobile / native app.** Design bundle viewport is fixed-width 1280px desktop.
- **No audio evluation** No ASR / pronunciation scoring from audio recordings
- **No English translations or glosses anywhere in the product.** The transcript is Spanish-only (no "+ Inglés" toggle), Phrase Autopsy is Spanish-only (grammar breakdown + why-it-sounds-native, no `natural`/`literal` English fields from the design bundle), Chunk Library entries are Spanish-only. The product targets B2 learners; English crutches push them back toward L1-mediated comprehension instead of the Spanish-internal reasoning the level demands. This is a permanent product position, not a deferral.

## Tech Stack

**Backend (implemented):**
- Python 3.12, FastAPI (`fastapi[standard]>=0.121.0`)
- SQLModel + Alembic, PostgreSQL via `psycopg2-binary`
- Prefect 3.x for the video-processing flow (in-process, with in-memory `flow_runs` dict for status)
- Anthropic SDK (Claude) for question generation and dialect classification — currently pinned to `claude-4-sonnet-20250514` / `claude-sonnet-4-20250514`
- OpenAI SDK (Whisper `whisper-1`, `verbose_json`, segment granularity) for transcription
- Google API client + `youtube-transcript-api` + `yt-dlp` for YouTube discovery, transcript fetch, and audio download
- spaCy with `es_dep_news_trf` (CUDA-enabled) for fill-in-the-blank candidate selection
- `isodate` for ISO 8601 duration parsing
- System dep: `ffmpeg`
- Container: Astral `uv` slim Python 3.12 image; CORS open to `localhost:3000`

**Frontend (planned, not yet started):**
- Per design bundle: HTML/CSS/JS prototype using React 18 UMD + Babel-standalone for design-tool playback only — production target is a real React (or equivalent) build that the team chooses.
- Fonts: Inter (UI), Instrument Serif (editorial accents), JetBrains Mono (numbers, grammar tags)
- Color: warm-neutral tokens via `oklch()`, terracotta accent (`#c4663d`); themes: `dark` (default, `#1c1914`), `paper`, `sepia`, `cool`
- No package manager, bundler, or framework decision is committed yet.

## Testing Suite

**None.** No `tests/` directory, no test runner config in `pyproject.toml`, no CI config in the repo, and `CLAUDE.md` states "No test suite or linter is currently configured."

## Audit Notes

### Capabilities Observed

Backend, as implemented:

1. **YouTube search** (`GET /api/videos/search`) — Data API v3, returns title, thumbnail, duration, view count.
2. **Pre-process dialect classification** (`GET /api/videos/search/classify/{video_id}`) — fetches a 3 KB transcript sample via `youtube-transcript-api`, classifies with Claude.
3. **Async video processing** (`POST /api/videos/process-async`) — kicks off a Prefect flow in a FastAPI `BackgroundTask`; deduplicates by `youtube_id` unless `force=true`.
4. **Sync video processing** (`POST /api/videos/process`) — legacy path, does NOT persist to DB.
5. **Flow status polling** (`GET /api/videos/status/{flow_run_id}`, `GET /api/videos/flows`) — backed by an in-memory dict.
6. **Video CRUD** (`GET /api/videos/`, `GET /api/videos/{video_id}`) — by YouTube ID.
7. **Segment fetch** (`GET /api/videos/{video_id}/segments`) — lazy-extracts from stored full transcript JSON if not yet materialised.
8. **MCQ progress tracking** (`POST/GET/DELETE /api/videos/{video_id}/progress`) — single-user, no auth.
9. **Post-process dialect classification** (`GET /api/videos/{video_id}/classify`) — re-runs Claude over the stored transcript.
10. **Fill-in-the-blank exercise generation** — spaCy POS-tag–driven, three difficulty levels (`facil`/`medio`/`dificil`), priority-weighted toward subjunctive verbs, `por`/`para`/`a`, object pronouns, and connectors. Default difficulty hard-coded to `medio` in the flow.

### Gaps and Inconsistencies

**Bugs / dead code worth flagging:**

- **Duplicate dialect-classification logic.** `services/dialect_classifier.py` and `repositories/classifier_repository.py` both implement the same Claude prompt. The repository version is what `GET /{video_id}/classify` uses; the service version is what `GET /search/classify/{video_id}` uses. Either consolidate or delete the unused one.
- **In-memory `flow_runs` dict** (`videos.py:29`) — flow status is volatile (lost on restart), unbounded (no eviction), and process-local (breaks under multi-worker deploys). The actual flow itself is implemented; only the status surface is unfinished. **The fix is persistence:** back the polling endpoints with a `processing_jobs` table keyed by `flow_run_id` and stop using the dict as the source of truth. Tracked as roadmap item 012.
- **Sync `/process` endpoint never saves to DB** and uses `return HTTPException(...)` instead of `raise` (`videos.py:355,357`) — that means errors return a 200 with the exception object as the response body. Looks like dead/legacy code.
- **404 message typos** — `"Flow encontrado"` and `"Video encontrado"` should both be `"… no encontrado"` (`videos.py:178,216`).
- **Anthropic model IDs are stale.** `claude-4-sonnet-20250514` and `claude-sonnet-4-20250514` are pre-Sonnet-4.6 / Opus 4.x. Current most-capable Claude is Opus 4.7 (`claude-opus-4-7`); for cost-sensitive tasks Haiku 4.5 (`claude-haiku-4-5-20251001`). Worth deciding which model fits each task before adding more.
- **`config.py:18-23` raises at import time** if any API key is missing. This makes the backend impossible to import for unit tests or local-only development paths. Default to lazy validation in service constructors.
- **`from db.py:create_db_and_tables`** is unused (Alembic owns schema). Safe to delete.
- **`main.py` imports `os` twice** (`main.py:1` and `main.py:6`).
- **CORS is hard-coded to `localhost:3000`.** Production deploy will need this externalised.

**Schema gaps for the planned frontend:**

The design bundle implies capabilities the backend does not yet support:

- **Phrase Autopsy data model** — `data.js:164` shows `{ natural, literal, grammar: [{tag, text}], natural_notes: [...], register }` keyed by phrase. Per §Non-Goals, the `natural` and `literal` English fields are dropped; the shipping shape is `{ grammar: [{tag, text}], natural_notes: [...], register }` — Spanish-only. No DB table, no generator service, no endpoint. Still the largest backend gap.
- **Token-level transcript with "interesting" markers.** Design uses `tokens: [{t: 'word'}, {t: 'word', w: true}, {p: ','}]`. Backend stores plain `transcript_text` per segment with no token boundaries or word-level annotations.
- **Saved-phrase / chunk library.** `data.js:198` shows phrases with `gloss`, `source`, `saved` (timestamp), `mastery` (0-1), `prompts: [...]`. No DB table.
- **User profile / streak / weekly stats.** Home screen shows "Ana · B2 · Día 6", "Esta semana 42min", "Comprensión 84 %". No users table, no session-time tracking, no aggregate computation.
- **Speaking-prompt recordings.** `screens-home.jsx:90-95` toggles a recording state but no upload/storage/feedback.

### Uncertain Areas

- Whether the existing `dialect` classification surfaces in the planned frontend, or is purely an internal signal for content curation.
- Whether the frontend will choose React (matching the prototype) or another framework. The prototype is HTML/CSS/JS; per the bundle README, the build is meant to be re-done in whatever fits.
- Whether the chunk library is per-user (multi-user future) or single-user singleton.
- Whether speaking-prompt recordings are intended to be transcribed/scored, or kept locally for personal playback.
- The expected source of Phrase Autopsy data: pre-generated by Claude at processing time (and stored), generated on-demand per tap, or hand-curated. The prototype hard-codes two phrases — implementation choice is wide open.
- Whether the new frontend will be served by FastAPI as a static bundle or run as a separate process (current CORS suggests separate process on `:3000`).
