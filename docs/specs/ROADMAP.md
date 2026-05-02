# Roadmap

<!-- status: inferred -->
| Field | Value |
|---|---|
| status | approved |
| created | 2026-05-02 |

## Features

| ID  | Feature                                              | Status        | Spec |
|-----|------------------------------------------------------|---------------|------|
| 001 | YouTube search                                       | implemented   | —    |
| 002 | Pre-process dialect classification (transcript sample) | implemented | —    |
| 003 | Async video processing pipeline (Prefect flow)       | implemented   | —    |
| 004 | Whisper timestamped transcription                    | implemented   | —    |
| 005 | Claude-generated timestamped MCQs (5 per video)      | implemented   | —    |
| 006 | Transcript-segment extraction & storage              | implemented   | —    |
| 007 | spaCy fill-in-the-blank exercise generation          | implemented   | —    |
| 008 | Video CRUD endpoints (list, get-by-youtube-id)       | implemented   | —    |
| 009 | MCQ answer-progress tracking (single-user)           | implemented   | —    |
| 010 | Post-process dialect classification (full transcript) | implemented  | —    |
| 011 | Synchronous `/process` endpoint (legacy)             | deprecated    | —    |
| 012 | Persist flow status (replace in-memory `flow_runs` dict with a `processing_jobs` table) | implemented | [012-flow-status-persistence/spec.md](./012-flow-status-persistence/spec.md) |
| 013 | Frontend: project setup & shared shell (rail + topbar + theme tokens) | planned | — |
| 014 | Frontend: Inicio (library + KPIs)                    | planned       | —    |
| 015 | Frontend: Escuchando (video, scrubber, transcript, MCQ rail) | planned | —    |
| 016 | Frontend: Phrase Autopsy side panel                  | planned       | —    |
| 017 | Backend: Phrase Autopsy data model + Claude generator | planned      | —    |
| 018 | Backend: token-level transcript with "interesting word" annotations | planned | — |
| 019 | Backend: chunk library schema + endpoints            | planned       | —    |
| 020 | Frontend: Mis frases (chunk library + speaking prompts) | planned    | —    |
| 021 | Backend: speaking-prompt audio recording upload      | planned       | —    |
| 022 | Backend: user profile + streak + weekly KPIs         | planned       | —    |
| 023 | Tweaks panel (theme, accent, transcript size, level badges) | planned | —    |
| 024 | Configurable difficulty for fill-in-blank exercises  | planned       | —    |
| 025 | Test infrastructure + ruff bootstrap (pytest + DB fixture + CI) | implemented | [025-test-infrastructure/spec.md](./025-test-infrastructure/spec.md) |
| 026 | Refresh Anthropic model IDs to current (Opus 4.7 / Sonnet 4.6 / Haiku 4.5) | planned | — |

## Status Values

- `planned` — not yet started
- `in-progress` — spec written, implementation underway
- `implemented` — decision record complete
- `deprecated` — removed from product

## Revision History

| Date       | Change                                                      |
|------------|-------------------------------------------------------------|
| 2026-05-02 | Initial roadmap inferred by audit skill. Backend features 001–010 marked `implemented`; legacy sync endpoint 011 marked `deprecated`; flow-status persistence (012) marked `in-progress` — the flow itself ships, only the polling surface needs a `processing_jobs` table. Frontend features 013–016, 020, 023 marked `planned` based on `docs/artefacts/` design bundle; backend follow-ups (017–019, 021, 022, 024, 025, 026) added as gaps surfaced in OVERVIEW audit notes. |
| 2026-05-02 | 012 → `implemented`. `processing_jobs` table replaces the in-memory dict; `/status` response trimmed (drops `result`, adds `youtube_video_id` + `video_id`); `/flows` paginates. Shipped without automated tests — 025 (test suite bootstrap) is the next prerequisite before further backend work. |
| 2026-05-02 | 025 → `in-progress`. Spec drafted: pytest + DB fixture (SQLite-first, Postgres-via-services-container as fallback) + monkeypatched service singletons + ruff (lint+format) + GitHub Actions. |
| 2026-05-02 | 025 → `implemented`. SQLite path landed (one dialect guard in migration `c6440d9b9453`); 17 tests across 4 files; ruff-clean codebase after audit-flagged cleanups (duplicate `import os`, unused `create_db_and_tables`, bare except). Decision record at `025-test-infrastructure/decision.md`. |
