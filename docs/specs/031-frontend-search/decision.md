# Decision Record: Frontend video search (Buscar) + add-to-library

| Field | Value |
|---|---|
| id | 031 |
| status | implemented |
| created | 2026-06-28 |
| spec | [spec.md](./spec.md) |

---

## Context

Adding a video meant hand-curling `POST /api/videos/process-async`; the search
endpoint had never been reachable from the app. 031 adds the **Buscar** screen
that closes that gap for the single B2 learner. The backend search/process/status
endpoints all already existed, so the work was overwhelmingly frontend — but two
real backend defects surfaced during implementation and manual smoke and were
fixed here rather than deferred:

1. **Search had no error handling** (the OVERVIEW-flagged wart): a
   `googleapiclient.errors.HttpError` (quota/transient) propagated as an opaque
   500. Folded in per the approved spec.
2. **`process-async` blocked until the flow finished** (discovered live, after the
   UI was wired). `run_flow_background` was `async def` and ran the blocking,
   multi-minute `process_video_flow` directly on the event loop. Starlette flushed
   the `PENDING` response to the transport buffer, then the coroutine starved the
   loop before those bytes reached the socket — so the POST didn't return until the
   job completed, the frontend learned `flow_run_id` only at the end, and `/status`
   was **never polled**. This made 031's core poll→route path untestable until
   fixed. Not in the spec; discovered and fixed because 031 depends on it.

Both resolved open questions held: per-card poll state with no queue;
`max_results=12`.

## Decision

A `/search` route (auto-registered via `routeTree.gen.ts`) plus a "Buscar" rail
entry (reusing the existing `IconSearch`). Search is **explicit-submit** (Enter/
button), not type-ahead — each `youtube.search().list` costs 100 quota units
against a 10k/day default. Results reuse the library card grid (`.lib-grid` /
`.card` / `.thumb`) and are marked **"Ya añadido"** (→ `/listen`) via a single
batched `POST /api/videos/exists`. A per-card `<ResultCard>` owns the add
lifecycle: **procesar** → `processVideo`; `EXISTS` routes straight to
`/listen/{youtube_id}`; `PENDING` sets `flowRunId`, a `useQuery` with
`refetchInterval` polls `/status` every 2 s and auto-stops on a terminal status;
`COMPLETED` invalidates `["videos"]`/`["videos-list"]` and routes in; `FAILED`
renders the error inline (how an >1-hour video surfaces — no client duration
guard). Backend: `youtube_search` maps `HttpError → YoutubeSearchError → 503`, and
`run_flow_background` is now a plain `def` so Starlette runs it in its threadpool,
off the event loop.

---

## Alternatives Considered

### 031↔032 boundary — how far the processing handoff goes

**Option A — fire + acknowledge only** (toast, defer all polling/routing to 032)
- Pros: cleanest split
- Cons: 031 alone gives no completion feedback; not independently useful

**Option B — poll to completion, then route** (inline status, route on COMPLETED)
- Pros: 031 is useful on its own — the learner who adds a video is carried in
- Cons: overlaps 032 (which adds the *global/persistent* in-flight view)

**Chosen:** B (spec discovery). 032 remains the global jobs surface, not the basic
single-add feedback.

### Search trigger — type-ahead vs explicit submit

**Chosen: explicit submit.** A debounced type-ahead would spend 100 quota units
per keystroke-batch and exhaust the daily 10k in a few sessions. Search fires on
Enter/button only. (Key decision in spec.)

### Where the `process-async` blocking fix lives

**Option A — wrap just the blocking call** (`await run_in_threadpool(process_video_flow, …)`, keep `async def`)
- Pros: surgical
- Cons: leaves the function async while its body is entirely synchronous

**Option B — make `run_flow_background` a plain `def`**
- Pros: Starlette auto-offloads non-coroutine background tasks to its threadpool;
  the whole body is already sync (DB marks + flow), so this is both minimal and
  more honest; running the sync Prefect flow in a no-loop thread is also cleaner
  than on the main loop thread
- Cons: none material for a single-user app (threadpool default 40 workers)

**Chosen:** B.

### Per-card vs single-active processing

**Chosen: per-card `<ResultCard>` state, no queue** (resolved OQ1). Each card holds
its own `flowRunId` and poll; firing several runs them as the backend allows
(contending for the spaCy model — the known single-process limitation).

---

## Tradeoffs

- **EXISTS is silent.** An already-processed video redirects instantly with no
  "ya estaba procesado" beat. Intended (spec chose immediate routing), but it's why
  the poll path looked "missing" until a genuinely new video was tried.
- **No reprocess affordance.** `processVideo` never sends `force=true`, so there's
  no way to re-run an existing video from Buscar (out of scope). The only way to
  exercise the poll path is a never-added `youtube_id`.
- **No client duration guard.** Over-1-hour videos are submitted and fail at
  processing; the learner sees the FAILED message rather than being stopped
  up-front. Deliberate (keeps the UI thin; the cap is a backend concern).
- **Threadpool, not a worker queue.** The blocking fix moves the flow off the event
  loop but it still runs in-process on a bounded threadpool; concurrent adds
  contend for the spaCy GPU model and API limits. A real worker pool is still
  unbuilt — acceptable for single-user.
- **Frontend stays manual-smoke.** Search needs the live YouTube API and processing
  needs the real multi-minute pipeline, so the poll→route lifecycle has no
  automated test (same posture as 015/020/028); it was verified in-browser.

---

### Spec Divergence

The implementation matches the spec's scope, endpoints, KPI/flow semantics, and
both resolved open questions. One addition beyond the written spec:

| Spec Said | What Was Built | Reason |
|---|---|---|
| Backend change = the search 503 hardening only | Also made `run_flow_background` a plain `def` (threadpool, non-blocking) | Discovered during manual smoke: as `async def` it blocked the event loop so `process-async` never returned until the flow finished and `/status` was never polled — 031's core path didn't work without it. |

No other divergence — `/search` route + rail entry, explicit-submit, `/exists`
marking, EXISTS-routes / PENDING-polls / FAILED-inline, and the 503 mapping all
match.

---

## Spec Gaps Exposed

- **The async-pipeline blocking bug is a pre-existing defect in 003/012's
  `process-async`, not a 031 gap** — but 031 is what surfaced it (no UI had ever
  exercised the poll path). ARCHITECTURE already flagged "background flow is
  `BackgroundTasks`… runs on the FastAPI event loop"; this makes the cost concrete
  (it didn't just contend — it blocked the response). Worth a one-line ARCHITECTURE
  note that the flow now runs in the threadpool.
- **`temp/` was never gitignored** (yt-dlp scratch dir); a smoke run left audio in
  the working tree. Added to `.gitignore` here.
- The spec held up; no OVERVIEW gap.

---

## Test Evidence

3 new backend tests for the search 503 hardening; full suite green on Postgres.
The process→poll→route lifecycle is frontend manual-smoke (live YouTube API +
real pipeline can't run headless) — verified in-browser: a new `youtube_id`
returns `PENDING` immediately, `/status` polls every 2 s through
`PENDING→RUNNING→COMPLETED`, then routes to `/listen`; the EXISTS short-circuit
routes straight in.

```
$ uv run pytest tests/test_search_route.py -v -p no:warnings
collected 3 items
tests/test_search_route.py ...                                           [100%]
============================== 3 passed in 7.50s ===============================
```

```
$ uv run pytest -p no:warnings
..............................................................           [100%]
134 passed in 13.06s
```

Frontend `pnpm lint` / `typecheck` / `build` green; SSR `curl /search` → 200
(heading + pre-submit state render pre-hydration, no browser APIs at module
scope). The `useExhaustiveDependencies` finding on the terminal-transition effect
was fixed honestly via a `useCallback`-stabilized `goToListen` + real deps (no
lint suppressions). Manual smoke confirmed by the operator: new-video poll→route
and EXISTS short-circuit both work.
