# Spec: Frontend video search (Buscar) + add-to-library

| Field | Value |
|---|---|
| id | 031 |
| status | approved |
| created | 2026-06-28 |

---

## Why <!-- required -->

The backend can search YouTube (`GET /api/videos/search`) and process a video
(`POST /api/videos/process-async`) — both have worked since items 001/003 — but
there is no UI for either. Adding a video today means hand-crafting a `curl` to
`process-async`, and the search endpoint has never been reachable from the app.
The design bundle's three screens (Inicio / Escuchando / Mis frases) simply never
included a find-and-add flow. 031 closes that gap: a **Buscar** screen where the
learner searches YouTube, sees which results are already in their library, and
adds a new one with a single click that carries them through processing and into
the listening view.

### Consumer Impact <!-- required -->

The single self-directed B2 learner (OVERVIEW "Target Consumer" — single-user, no
auth). They benefit directly and obviously: the core "add a video I'm interested
in" action — the entry point to the entire product — becomes a first-class screen
instead of a developer-only `curl`. Without 031 the app can only ever show videos
that were seeded by hand.

### Roadmap Fit <!-- required -->

031 is the first of the two find-and-add items (031 search + add, 032 the richer
processing-status surface). It depends on no unbuilt backend — `GET /search`,
`POST /process-async`, `GET /status/{flow_run_id}`, and `POST /exists` (027) all
exist and `GET /search` was verified operable end-to-end while scoping this
(HTTP 200 + real results, CORS from `:3000` OK). 031 deliberately includes a
**poll-to-completion** handoff so it is useful on its own; **032** later layers a
global in-flight-jobs view on top (e.g. resume polling across navigations, list
all PENDING/RUNNING jobs). 031 also folds in the small backend hardening that the
search endpoint needs regardless (unhandled `HttpError` → opaque 500).

---

## What <!-- required -->

### Acceptance Criteria <!-- required -->

- [ ] A **Buscar** entry in the rail opens a `/search` screen with a search box.
- [ ] Submitting a query (Enter or a button — not type-ahead) calls
      `GET /api/videos/search` and renders results: thumbnail, title, channel,
      duration, view count.
- [ ] Results already in the library are marked "Ya añadido" and link to
      `/listen/{youtube_id}` instead of offering "procesar" (via `POST /exists`).
- [ ] Clicking **procesar** on a new result starts processing
      (`POST /api/videos/process-async`):
  - if the backend returns `EXISTS`, the learner is routed straight to
    `/listen/{youtube_id}`;
  - otherwise the result shows an inline **Procesando…** state that polls
    `GET /api/videos/status/{flow_run_id}` and, on `COMPLETED`, routes to
    `/listen/{youtube_id}` with the library/rail reflecting the new video.
- [ ] A `FAILED` job shows the error inline (this is how an over-1-hour video
      surfaces — it is submitted and fails at processing, by design) without
      breaking the rest of the screen.
- [ ] When YouTube search itself errors (quota/transient), the backend returns a
      clean **503** and the UI shows "Búsqueda no disponible, intenta de nuevo"
      rather than a generic failure or an opaque 500.

### Non-Goals <!-- required -->

- **No dialect preview.** `GET /search/classify/{id}` is not called from the
  results list (deferred — extra per-result call, 404s without a YT transcript).
- **No 1-hour pre-filter/guard.** Over-cap videos are submitted and fail at
  processing; the FAILED state surfaces it. No client-side duration gate.
- **No global in-flight-jobs view / cross-navigation resume.** Polling lives on
  the Buscar screen for the current session; the persistent jobs surface (and
  `GET /flows`) is **032**.
- **No playlist/channel search** (backend already restricts `type=video`), **no
  bulk/multi-add queue**, **no in-app preview** of a result before adding.
- **No search history / saved searches / pagination** — a single page of results
  (backend `max_results` 1–25) is enough for v1.
- **No library curation** (edit/delete/re-order videos) from Buscar.

### Open Questions <!-- optional -->

Both resolved at approval (2026-06-28) with the proposed defaults:

1. **Concurrent processing.** ✅ Resolved → **per-card state, no queue**. Each card
   tracks its own `flow_run_id` and polls independently; the learner may fire
   several and they run as the backend allows (FastAPI `BackgroundTask` on the
   event loop, contending for the spaCy GPU model per ARCHITECTURE "Single FastAPI
   process"). No client-side serialization or queue in 031.
2. **Results per search.** ✅ Resolved → **12** (`max_results=12`, within the
   backend's 1–25 range).

---

## How <!-- required -->

### Approach <!-- required -->

**Backend (one small hardening change):**

- `src/services/youtube_search.py` / `src/api/routes/videos.py:58` — wrap the
  `search_videos` call (the two `.execute()` calls) so a
  `googleapiclient.errors.HttpError` (quota, transient, disabled key) maps to
  `HTTPException(status_code=503, detail="…")` instead of propagating to a 500.
  Empty/whitespace query already 400s. No new endpoint, no schema, no migration.

**Frontend (`webapp/`, the bulk of the work):**

- *Route* `src/routes/search.tsx` (`/search`) + a **Buscar** item in
  `src/components/Rail.tsx` (under "Estudio", alongside Inicio).
- *API + types* (`src/lib/api.ts`, `api-types.ts`): `searchVideos(query, max)` →
  `{ results: SearchResult[] }`; `checkVideosExist(ids)` → `{ present, missing }`
  (wraps `POST /exists`); `processVideo(url, force?)` → the `EXISTS | PENDING`
  union; `getFlowStatus(flowRunId)` → `{ status, youtube_video_id, video_id,
  error? }`. `SearchResult` mirrors the live shape (`video_id`, `url`, `title`,
  `thumbnail`, `channel_title`, `duration`, `duration_formatted`, `view_count`,
  `view_count_formatted`).
- *Search* is **explicit-submit** (form onSubmit / Enter), not debounced
  type-ahead — see Key Decisions. `useQuery` keyed `["search", submittedQuery]`,
  `enabled` only once a query is submitted.
- *Already-in-library marking*: after results load, one `checkVideosExist(result
  ids)` call (keyed `["exists", ids]`); results in `present` render "Ya añadido"
  → `<Link to="/listen/$id">`, the rest render a **procesar** button.
- *Process + poll lifecycle*: a `useMutation` fires `processVideo(result.url)`.
  - `EXISTS` → `router.navigate({ to: "/listen/$id", params: { id: youtube_id } })`.
  - `PENDING` → store the `flow_run_id` in per-card state; a `useQuery` keyed
    `["flow-status", flow_run_id]` with `refetchInterval` while status is
    `PENDING`/`RUNNING` (interval cleared otherwise). On `COMPLETED`: invalidate
    `["videos"]` / `["videos-list"]` (so Inicio + rail update) and navigate to
    `/listen/{youtube_id}` (the id is the result's own `video_id`, also echoed as
    `status.youtube_video_id`). On `FAILED`: stop polling, render `status.error`
    inline on the card.
- All browser API access (router, fetch) stays in handlers/effects → SSR-safe,
  consistent with 015/020/028.

### Confidence <!-- required -->

**Level:** Medium

**Rationale:** Every endpoint exists and the search path is verified working, so
there's no backend unknown beyond the trivial 503 wrap. The frontend is standard
react-query wiring. The one part with moving pieces is the **process → poll →
route** handoff: not double-firing the mutation, clearing the poll interval on
terminal states, invalidating the right caches so the new video appears, and
routing on the correct id. This is the same class of effect-lifecycle work that
015 (MCQ-due latch) and 020 (deep-link seek) handled, so the risk is known and
contained to one screen.

**Validate before proceeding:** a localhost end-to-end smoke —
1. **EXISTS path** (cheap): search a term that surfaces the already-seeded
   `m1DFpkNdcv0`, confirm it shows "Ya añadido" and links to `/listen`; force a
   re-add of a known video and confirm `EXISTS` routes straight to `/listen`.
2. **New-video path** (one real run, ~minutes): procesar a short (<5 min) new
   video, confirm the inline state polls PENDING→RUNNING→COMPLETED and routes to
   `/listen/{id}` with the video now in the library/rail.
3. **FAILED path**: procesar an >1-hour video, confirm the card shows the failure
   message and the screen stays usable.
4. **503 path**: unit-test the backend wrap (monkeypatched `HttpError`).

### Key Decisions <!-- optional -->

- **Explicit-submit search, not type-ahead.** Each `youtube.search().list` costs
  **100 quota units** against a default 10,000/day; debounced type-ahead would
  exhaust the quota in a handful of sessions. Search fires on Enter/submit only.
- **Poll-to-completion lives in 031** (not deferred wholesale to 032) so the
  screen is independently useful — a learner who adds a video is carried into it.
  032's job is the *persistent/global* surface (resume across navigation, list
  all in-flight jobs), not the basic single-add feedback.
- **Route on the YouTube id, not the DB id.** `/listen/$id` is the youtube_id
  permalink contract (027/ARCHITECTURE). The submitted result's `video_id` *is*
  that id, so it's known up front; `status.youtube_video_id` corroborates it.
- **Backend 503 over a silent empty list.** A quota failure is a real, temporary
  outage the learner should see ("intenta de nuevo"), not an empty result set that
  reads as "no matches."

### Testing Approach <!-- required -->

Per OVERVIEW's posture: backend gets pytest; the frontend stays manual-smoke
(search needs the live YouTube API and processing needs the real multi-minute
pipeline — neither runs headless), same as 015/020/028.

**Backend (pytest on Postgres):**
- `GET /api/videos/search` maps a `googleapiclient.errors.HttpError` (monkeypatched
  on `youtube_search.search_videos`) to a **503** with a clean detail — the new
  hardening. Empty-query still 400s.

**Frontend (manual smoke + build):**
- The four validation paths above (EXISTS link, EXISTS re-add route, new-video
  poll→route, FAILED inline, 503 banner).
- `pnpm lint` / `typecheck` / `build` green; SSR sanity via `curl /search` (route
  matches, renders pre-hydration without touching browser APIs at module scope).
