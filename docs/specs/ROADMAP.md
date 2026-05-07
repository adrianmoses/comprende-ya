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
| 013 | Frontend: project setup & shared shell (rail + topbar + theme tokens) | implemented | [013-frontend-project-setup/spec.md](./013-frontend-project-setup/spec.md) |
| 014 | Frontend: Inicio (library + KPIs)                    | implemented   | [014-inicio/spec.md](./014-inicio/spec.md) |
| 015 | Frontend: Escuchando (video, scrubber, transcript, MCQ rail) | implemented | [015-escuchando/spec.md](./015-escuchando/spec.md) |
| 016 | Frontend: Phrase Autopsy side panel                  | implemented   | [016-phrase-autopsy/spec.md](./016-phrase-autopsy/spec.md) |
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
| 2026-05-03 | 013 → `in-progress`. Spec drafted: TanStack Start (recommended) vs plain Vite + TanStack Router (fallback) for the frontend toolchain; `webapp/` at repo root; rail + topbar + 4-theme tokens ported from the design bundle; dev port 3000 to match backend CORS; placeholder routes for Inicio / Escuchando / Mis frases; API smoke call to `GET /api/videos/`; no frontend tests yet (deferred). |
| 2026-05-03 | 013 → `implemented`. TanStack Start landed (no fallback needed). Tailwind v4 stripped post-scaffold (CLI forces it, but plain CSS is a clean replacement). SSR retained as default — eliminates FOUC for the `data-theme="dark"` attribute, deviates from spec §Non-Goals "client-rendered SPA" but justified in `decision.md`. Lint/typecheck/build all green. Decision record at `013-frontend-project-setup/decision.md`. |
| 2026-05-03 | 014 → `in-progress`. Spec drafted: Inicio page = greeting + 4 KPI placeholders + Continúa escuchando + Tu biblioteca, wired against `GET /api/videos/` and `GET /api/videos/{id}/progress`. KPI values stay as `—` / `0` until 022 lands real aggregates. Adds `@tanstack/react-query` for cross-screen data caching. Generated thumbnails (HSL hash) over YouTube thumbnails to keep payload lean and aesthetic consistent. |
| 2026-05-03 | 014 → `implemented`. `@tanstack/react-query` 5.100.9 wired with a single shared `QueryClient` in `__root.tsx`. `useQuery` for the videos list + `useQueries` for parallel per-video progress; cards link via the typed-params form `<Link to="/listen/$id" params={{ id: video.video_id }}>`. Fixed the `questions: number` → `Array<VideoQuestion>` type bug from 013 (only `routes/index.tsx` consumed it). Backend response uses `user_answer` (not `selected_answer`) and `video_id: string` (YouTube id, not DB id) — types corrected. Lint/typecheck/build green. Decision record at `014-inicio/decision.md`. |
| 2026-05-03 | 015 → `in-progress`. Spec drafted: Escuchando = real YouTube iframe player + scrubber with question marks + transport ±5s/speed + plain transcript with current-segment highlight + right rail with auto-pausing MCQ panel and always-on session panel. Wires against `GET /api/videos/{id}`, `GET /api/videos/{id}/segments` (DB id, not YouTube id — backend wart noted as Open Question), and `POST /api/videos/{id}/progress`. Phrase Autopsy / tappable words / save-phrase deferred to 016/020. Confidence Medium — two pre-impl spikes flagged: YouTube IFrame API + SSR hook, MCQ-due "fire once" effect logic. |
| 2026-05-03 | Architecture: **no English translations or glosses anywhere in the product.** Recorded as a permanent non-goal in OVERVIEW.md. Affects 015 (no "+ Inglés" toggle on the transcript), 016/017 (Phrase Autopsy data shape narrows to Spanish-only `{ grammar, natural_notes, register }` — drops the design's `natural`/`literal` English fields), 020 (Chunk Library entries Spanish-only). Reasoning: B2 learners should reason inside Spanish; English crutches regress them to L1-mediated comprehension. |
| 2026-05-03 | 015 → `implemented`. Real YouTube IFrame API embed via SSR-safe `useYouTubePlayer` hook (`@types/youtube` 0.2.0 added; `Window` augmentation lives in `src/types/youtube-window.d.ts` to dodge TS's UMD-in-module warning). Scrubber + transport + transcript with `is-current` highlight + auto-pausing MCQ panel + always-on session panel. First uses of `useMutation` and `useQueryClient` in the project; narrow invalidation on `['video-progress', youtubeId]` makes Inicio's progress bars update on back-navigate without a refetch flash. MCQ-due effect uses pending-latch + answered-set gating. Backend `/segments` int-id wart worked around via chained queries; cleanup deferred. Lint/typecheck/build green; SSR sanity (curl) clean. Decision record at `015-escuchando/decision.md`. |
| 2026-05-05 | 016 → `in-progress`. Spec drafted: frontend-only Phrase Autopsy side panel, fixture-backed (`webapp/src/data/autopsy-fixtures.ts`), with a temporary "Frases destacadas" list trigger in the right rail (clearly marked `temporal · ver 018`) until tappable transcript words land in 018. Two layers (Gramática, Por qué suena natural) — the design's English "Significado natural" layer is permanently dropped. Save toggle is session-local until 020. Aside priority: MCQ wins over autopsy. Confidence High. |
| 2026-05-06 | 016 → `implemented`. AutopsyPanel + AutopsyTriggerCard ship; fixture seeds two phrases on `m1DFpkNdcv0`. Two deliberate spec deviations: (1) reused the existing `.btn` system in `shell.css` (extended with `.primary` and `.accent` modifiers ported from the design) instead of autopsy-scoped `.btn-save`/`.btn-replay` — converges button vocabulary for 020. (2) Replaced the spec's IIFE-in-JSX pattern with a `const autopsyEntry` above the JSX, matching the existing `pendingQuestion` shape. Lint/typecheck/build green; SSR smoke (curl) renders the trigger card pre-hydration. Decision record at `016-phrase-autopsy/decision.md`. |
