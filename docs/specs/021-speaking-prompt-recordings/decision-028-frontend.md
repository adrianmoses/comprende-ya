# Decision Record: Speaking-prompt recordings — frontend cutover (028)

| Field | Value |
|---|---|
| id | 028 |
| status | implemented |
| created | 2026-06-27 |
| spec | [021 spec.md](./spec.md) (frontend acceptance criteria) |
| backend | [021 decision.md](./decision.md) |

---

## Context

021 shipped the recording backend and its OQ1 gate passed (browser
`audio/webm;codecs=opus` round-trips and plays back as-stored). But the feature
was unreachable from the app — `ChunkCard.tsx` still carried the 020 stub: a 3.5s
`REC_STUB_MS` `setTimeout` capturing no audio. 028 is the cutover that makes the
recording loop real for Ana on the Mis frases screen.

It was scoped as its own roadmap item (mirroring the repo's 019-backend /
020-frontend split) rather than folded into 021, so the backend could ship and be
gated independently. The spike done during 021 had already proven the exact client
recipe end-to-end (`getUserMedia` → `MediaRecorder` → multipart `POST` →
`<audio>`), so this was low-risk wiring of a known-good path into the real UI — no
format unknowns remained.

One real bug surfaced during the manual smoke that the backend's own tests could
not have caught: playback served **stale browser-cached audio**. That is recorded
below as a spec gap and was fixed as part of this work.

## Decision

The `ChunkCard` recording button is now wired to real microphone capture via a new
`useAudioRecorder` hook (`getUserMedia` + `MediaRecorder`, default mimeType,
30s max-duration auto-stop, track cleanup on stop/unmount, `denied`/`unsupported`
states). Stopping a recording fires a react-query upload mutation to `POST
/api/chunks/{id}/recording`, which invalidates `["chunks"]` so `has_recording`
refreshes across the app. When a chunk has a recording, the card renders a native
`<audio controls>` plus Regrabar / Borrar. Permission-denied and unsupported-browser
cases show an inline Spanish message and leave the button usable.

The shared `api()` wrapper was taught to skip its hardcoded JSON content-type when
the body is `FormData`, so the browser sets the multipart boundary. Playback uses
a native `<audio>` element pointed at `GET …/recording` — no custom transport, no
download step.

A backend bug found during smoke — the recording `GET` had no cache headers, so
the browser replayed stale audio after a re-record/reload — was fixed by sending
`Cache-Control: no-store` on that response, with a regression test.

All `navigator`/`MediaRecorder` access lives inside handlers/effects, so SSR is
unaffected (verified by build + a dev `curl` of `/chunks`).

---

## Alternatives Considered

### Playback control — native `<audio controls>` vs custom transport

**Option A — Native `<audio controls src=…>`.**
- Pros: zero custom code; browser handles play/seek/scrub; honest and accessible.
- Cons: visual styling is browser-default, not fully theme-matched.

**Option B — Custom play button + `Audio()` object.**
- Pros: full visual control to match the design tokens.
- Cons: re-implements transport, progress, a11y for a single-user voice memo.

**Chosen:** A. The spec explicitly allowed "an `<audio>` (or a play button)", and a
personal re-listen affordance doesn't warrant a hand-rolled player. The 30s cap
keeps clips short enough that default controls are fine.

### Where recording state + mutations live — ChunkCard vs the route

**Option A — Inside `ChunkCard`.** Each card owns its recorder hook + upload/delete
mutations + `recVersion`.
- Pros: recording is inherently per-card; co-locating state with the card keeps the
  `/chunks` route thin; cards are independent.
- Cons: each card instantiates a recorder hook (cheap — no work until `start()`).

**Option B — Lift to the `/chunks` route, pass handlers down.**
- Pros: one recorder instance.
- Cons: the route must track *which* card is recording; a single recorder can't
  model two cards mid-action; more prop plumbing for no real gain.

**Chosen:** A. Mirrors how `listen.$id.tsx` co-locates the chunk save/delete
mutations with their trigger. Per-card ownership is the natural model.

### Re-record freshness — frontend cache-bust vs backend no-cache header

**Option A — `?v=recVersion` query param bumped on each upload (frontend only).**
- Pros: no backend change.
- Cons: the counter resets to 0 on page reload and **collides with URLs the browser
  already cached** in a prior session → stale playback. This is exactly the bug that
  surfaced in smoke. Insufficient on its own.

**Option B — `Cache-Control: no-store` on the recording `GET` (backend).**
- Pros: fixes it at the source — the browser never caches a take, so every reload
  and every re-record fetches the current file. Correct regardless of client state.
- Cons: re-fetches small audio each play (negligible at single-user scale).

**Chosen:** B as the real fix, **plus** keeping the `recVersion` bump — not for
cache-busting but to change the `<audio>` element's `src` so it re-requests after an
in-session Regrabar (a native `<audio>` won't re-fetch a stable `src`). The two are
complementary: `no-store` guarantees fresh bytes, `recVersion` forces the element to
go ask for them.

### Upload mutation feedback — optimistic vs pending-only

**Option A — Pending-only.** Disable the button to "Subiendo…" while in-flight; flip
on success.
- Pros: truthful; no rollback animation; matches 020's save-button decision.
- Cons: a perceptible disabled beat during upload.

**Option B — Optimistic.** Show playback immediately, roll back on error.
- Cons: rollback on a failed upload is ugly; the take isn't really saved yet.

**Chosen:** A. Continues the 020 pending-only posture for consistency.

---

## Tradeoffs

- **Native `<audio>` over a themed player** — gives up pixel-matched styling for zero
  transport code and free a11y. The clip cap keeps the default control adequate.
- **`no-store` on every playback** — gives up HTTP caching of recordings (re-fetch on
  each play) to guarantee correctness after overwrite. Negligible for single-user,
  phrase-length audio; the alternative (heuristic caching) is precisely what broke.
- **Per-card recorder hooks** — each card holds its own recorder; cheap because the
  hook does nothing until `start()`, and it keeps the route free of "which card is
  recording" bookkeeping.
- **Default `MediaRecorder` mimeType** — relies on the recording and playback browser
  agreeing on format (safe under the single-user, same-browser assumption the 021
  gate validated). Cross-browser playback remains out of scope.
- **Frontend stays on manual smoke** — no automated coverage for the capture flow
  (`getUserMedia` can't run headless), consistent with the 014–020 posture. The
  backend half (including the new `no-store` header) is unit-tested.

---

### Spec Divergence

Implementation matched the plan faithfully. Notable as-built specifics:

| Plan/Spec Said | What Was Built | Reason |
|---|---|---|
| `?v=` cache-bust handles re-record freshness (plan Risk) | `?v=recVersion` kept **only** to force `<audio>` element reload; the actual cache fix is backend `Cache-Control: no-store` | The counter alone was insufficient — it resets on reload and collides with already-cached URLs. Found in smoke; fixed at the source. |
| Frontend-only scope (028 adds no backend changes) | One backend line changed: `no-store` on the recording `GET` + a regression test | A 021 caching bug only observable once a live `<audio>` consumed the endpoint. Fixing it here was correct rather than deferring. |
| Permission/`unsupported` handling | `denied` and `unsupported` statuses with distinct Spanish copy ("Permite el acceso al micrófono…" / "Tu navegador no permite grabar audio.") | As specced; copy finalized. |

---

## Spec Gaps Exposed

1. **The recording `GET` had no cache-control — a latent 021 bug.** 021's backend
   tests asserted status, bytes, and content-type, but nothing about cacheability,
   because `TestClient` never caches. Only a real browser `<audio>` element revealed
   that a re-record/reload replayed stale audio. The fix (`Cache-Control: no-store`)
   now has a regression test (`test_get_is_not_browser_cacheable`). Lesson: endpoints
   that serve mutable content at a stable URL need an explicit cache policy, and that
   policy is worth a test even when the unit harness can't observe a browser cache.

2. **`fastapi`'s `FileResponse` sets `etag`/`last-modified` but not
   `Cache-Control`.** Worth noting for any future file-serving endpoint in this repo
   — the default is browser-heuristic caching, which is wrong for overwrite-in-place
   resources.

3. **Smoke-only transition artifact.** Audio cached *before* the `no-store` fix
   persists until the browser cache is cleared (a plain reload doesn't always evict
   the `<audio>` media cache; DevTools "Disable cache" or a hard profile clear does).
   Not a code issue — a one-time migration wrinkle — but worth recording so it isn't
   re-debugged later.

No spec revisions warranted. No new roadmap items surfaced. The `alembic`
autogenerate drift (flagged in the 021 decision) remains the open follow-up for the
next schema-touching feature (022).

---

## Test Evidence

Backend — recording route tests, now 12 (added `test_get_is_not_browser_cacheable`):

```
$ uv run pytest tests/test_recording_routes.py
12 passed
```

Full backend suite — no regression:

```
$ uv run pytest
114 passed in 10.51s
```

Backend lint/format clean:

```
$ uv run ruff check src/ tests/   → All checks passed!
$ uv run ruff format --check …    → 51 files already formatted
```

Frontend quality gates (`webapp/`):

```
$ pnpm lint        → Checked 30 files. No fixes applied.
$ pnpm typecheck   → tsc --noEmit, clean
$ pnpm build       → ✓ built (client chunks 6.50 kB / server chunks 11.25 kB)
```

SSR sanity — `/chunks` renders server-side with no `navigator`-on-server crash:

```
$ curl -s -o /dev/null -w "%{http_code}" localhost:3000/chunks   → 200
# full app shell (rail, data-theme="dark") present in the rendered HTML
```

Live cache-header fix confirmed against the running dev server:

```
$ curl -sD - -o /dev/null localhost:8000/api/chunks/2/recording | grep -i cache-control
cache-control: no-store
```

Manual end-to-end smoke (operator, real mic, against `make dev`): record → upload
(`POST …/recording` 201) → `<audio>` playback of own voice → reload persists →
Regrabar overwrites and plays the new take → Borrar returns to no-recording →
permission-denied shows the Spanish message. Passed (one-time browser-cache clear
needed to evict audio cached before the `no-store` fix).
</content>
