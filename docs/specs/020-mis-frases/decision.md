# Decision Record: Mis frases (chunk library + speaking prompts)

| Field | Value |
|---|---|
| id | 020 |
| status | implemented |
| created | 2026-05-17 |
| spec | [spec.md](./spec.md) |

---

## Context

019 shipped the backend chunks library (`POST` / `GET` / `DELETE /api/chunks`, Claude-generated speaking prompts persisted at save-time) but had zero in-app consumers. The `/chunks` route was a 12-line placeholder, the Inicio "Frases guardadas" KPI was hard-coded `0`, the Rail's chunks badge carried a `// Real count comes with feature 020` comment, and the `AutopsyPanel` save toggle was a session-local `Set<string>` (`listen.$id.tsx:92`) that forgot every reload.

020 ships the Mis frases screen plus three out-of-route wirings that make the chunks library actually work end-to-end: AutopsyPanel save toggle → real `POST`/`DELETE` against a `["chunks"]` query, Inicio + Rail counts → same `["chunks"]` query (react-query dedupes the fetch), and `/listen/$id` → a `?t=` deep-link so the new "jump to source" affordance on chunk cards lands the user mid-video.

Stack continuation: TanStack Start + react-query + plain CSS port, same posture as 014–016. Frontend-tests-deferred posture continues (manual smoke is the bar). The spec's confidence bar of Medium-leaning-High held — both validation items (deep-link race; empty-body 204) resolved as planned with no surprise rework.

## Decision

Implemented the maximalist visual port: every design affordance from `screens-home.jsx:74-165` ships, with deferred-feature ones (mastery dots, recording capture, "Necesitan práctica" filter, "Empezar sesión de práctica" routing) shipping as honest visual stubs marked `Próximamente`. Real functionality covers: card grid + "recent" filter, header + sub-copy, prompt cycling, empty/loading/error states, source-title deep-link, AutopsyPanel save/unsave round-trip, Inicio KPI, Rail badge.

Single `["chunks"]` query key shared across four call sites (Rail, Inicio, `/chunks` route, `/listen/$id`); one save/delete mutation in `listen.$id.tsx` invalidates the key and updates all four views without manual refetch. `isSaved` is derived from the query data via a memoized `Map<normalized-phrase, Chunk>` keyed by `${video_id}|${normalize_phrase(phrase)}` — O(1) lookup, no local state to drift.

---

## Alternatives Considered

### `Necesitan práctica` filter chip UX while inert

**Option A — Visually disabled chip with `Próximamente` tooltip.**
- Pros: Telegraphs that the surface exists; 021 cutover is a handler swap. Matches 016's `temporal · ver 018` precedent.
- Cons: Chip still consumes row space without paying its way.

**Option B — Hide until 021.**
- Pros: Cleanest screen.
- Cons: Loses the three-filter rhythm; 021 has to (re)introduce the layout.

**Option C — Active but always shows "Nada por ahora" empty state.**
- Pros: Honest about emptiness.
- Cons: The copy lies softly ("nothing here" vs "feature not ready").

**Chosen:** A. Matches the spec recommendation and 016's precedent. Shipped with `chip is-disabled` + `aria-disabled="true"` + `title="Próximamente"`.

### Save round-trip — optimistic vs pending-only

**Option A — Optimistic.** Flip button state immediately, roll back on error.
- Pros: Feels instant when the network is fast.
- Cons: 1–3s Claude latency from 019's spike means the rollback animation is non-trivial; a 502 mid-save looks ugly.

**Option B — Pending-only.** Disable the button while in-flight; flip on success; surface inline error on failure.
- Pros: Truthful — the chunk isn't saved until the response lands. No rollback animation. The disabled button already telegraphs "working on it" given the bounded latency.
- Cons: 1–3s of disabled-button feedback is perceptible.

**Chosen:** B. Shipped exactly as spec recommended. The disabled-state CSS (`.btn:disabled, .btn.is-disabled { opacity: 0.55; cursor: not-allowed; }`) was added to `shell.css` as a one-shot system rule rather than scoped to autopsy, so the same modifier covers the inert filter chips and the "Empezar sesión" stub.

### Saved-state derivation — local `Set<string>` vs query-derived

**Option A — Keep 016's session-local `Set<string>`, hydrate it from `["chunks"]` on mount.**
- Pros: No re-derivation per render.
- Cons: Two sources of truth (the set + the cache). Bug-prone — invalidations have to push back into the set. The very problem we're fixing.

**Option B — Derive `isSaved` from the cached `["chunks"]` query on every read.**
- Pros: Single source of truth. Cache invalidation = visual update for free.
- Cons: Linear scan + `normalizePhrase` per chunk per read.

**Chosen:** B, with a memoization fix landed during `/simplify`. Build a `Map<normalized-phrase, Chunk>` filtered to the current `video_id` inside a `useMemo` keyed on `[chunksQuery.data, youtubeId]`; `savedChunkFor(phrase)` is then a one-line `map.get(normalizePhrase(phrase))`. O(1) per lookup, O(N) per query-invalidation only.

### `?t=` deep-link autoplay behaviour after the spike

**Option A — Auto-seek + auto-play on `?t=`.**
- Pros: Lands Ana at the exact moment with zero clicks.
- Cons: Browser autoplay policies may block play() with no preceding user gesture.

**Option B — Auto-seek only; require a tap to play.**
- Pros: Sidesteps autoplay restrictions.
- Cons: One extra click.

**Chosen:** A. The manual SSR + dev smoke during the spike did not surface an autoplay block in Chrome on darwin, and the source-link click that brings the user from `/chunks` to `/listen/$id?t=…` *is* a user gesture in the same browsing-context tick. If 021 surfaces an autoplay block in a different browser, the fallback is documented (drop the `player.play()` call and add a "Tap to play" hint near the player frame).

### Page-shell duplication

**Option A — Each branch (`MisFrases`, `ChunksSkeleton`, `ChunksErrorState`, `ChunksEmptyState`) renders its own `<div class=page><h1>Tu biblioteca de frases</h1>` wrapper.**
- Pros: Each branch is independently readable.
- Cons: Four copies of the header; any future copy change has to touch all four.

**Option B — Extract a `<MisFrasesShell>{children}</MisFrasesShell>` wrapper.**
- Pros: One header source. ChunksEmptyState becomes small enough to inline into `chunks.tsx` and delete its standalone file.
- Cons: One more component to read.

**Chosen:** B. Decided during the `/simplify` pass — the duplication crossed four call sites, which is past the threshold worth deduping. `ChunksEmptyState.tsx` (the file) was deleted; the empty state is now a private function in `chunks.tsx` that wraps `MisFrasesShell`.

---

## Tradeoffs

What the chosen approach optimises for:

- **Single source of truth for chunk state across the app.** Rail, Inicio, `/chunks`, and the AutopsyPanel inside `/listen/$id` all read the same `useQuery({ queryKey: ["chunks"], queryFn: listChunks })`. React-query dedupes the fetch and a single `invalidateQueries(["chunks"])` after a save/delete updates every view. Cost: every route now pays for the chunks fetch on mount, even if the user never looks at the badge — but the response is small (id, source_title, phrase, start_time, prompts, created_at; no audio, no transcript) and the cache is shared.
- **Maximalist visual port over progressive disclosure.** Mastery dots, recording button, the "Necesitan práctica" chip, and the "Empezar sesión de práctica" button all render today as visual stubs. Cost: the screen is busier than a strict MVP would be, and the disabled affordances need cutovers in 021. Benefit: the 021 cutover is a handler swap, not a layout change, and Ana sees the eventual product shape from day one.
- **Pending-only save UX.** The button disables for the 1–3s Claude takes to generate prompts at save-time. Cost: perceptible latency. Benefit: no optimistic-rollback edge cases, no fake-flip-then-revert animation on errors.
- **Hand-rolled Spanish relative-time formatter.** `webapp/src/lib/relative-time.ts` is 15 lines of hand-rolled "hoy"/"ayer"/"hace N días/semanas/meses" rather than `Intl.RelativeTimeFormat`. Cost: any locale that's not Spanish needs a rewrite. Benefit: full copy control (the `Intl` output is "hace 1 día" — losing the "ayer" warmth), zero deps.
- **`normalizePhrase` mirror in TS with an honesty comment.** `webapp/src/lib/normalize-phrase.ts` re-implements `src/repositories/autopsy_repository.py:normalize_phrase`. Python uses `casefold()`, JS uses `toLocaleLowerCase("es")` — equivalent for Spanish Whisper output, divergent on German ß / Greek final sigma. The comment now documents the divergence honestly rather than overclaiming parity. Cost: shared schema generation would kill the drift risk entirely, but is not worth it for two 1-liners. Benefit: no codegen pipeline, no runtime cost.
- **No in-screen delete on chunk cards.** Unsave is via the AutopsyPanel on `/listen/$id`. Symmetric with where save originated. Cost: Ana has to navigate back to the source video to remove a phrase. Benefit: less surface to maintain, the spec explicitly listed an in-screen × as out of scope, and `deleteChunk()` exists in the API client if it later proves necessary.

---

### Spec Divergence

Implementation matched the spec faithfully on every acceptance criterion. Two deliberate divergences happened during the `/simplify` pass *after* the spec's exact code samples were ported:

| Spec Said | What Was Built | Reason |
|---|---|---|
| `ChunksFilter` is `"all" \| "low" \| "recent"` with `"low"` falling through to return all chunks (Open Question §1) | `ChunksFilter` is `"all" \| "recent"`; the dead `"low"` branch was removed | The "Necesitan práctica" chip is `is-disabled` with no `onClick` — `"low"` was never dispatched. Dropping it removes unreachable code; 021 will reintroduce the variant when the chip becomes active. |
| Each branch (`MisFrases`, `ChunksSkeleton`, `ChunksErrorState`, `ChunksEmptyState`) renders its own `<div class=page><h1>` shell (per the §How code samples) | Extracted a `<MisFrasesShell>` wrapper in `chunks.tsx`; `ChunksEmptyState.tsx` was inlined into `chunks.tsx` and the standalone file deleted | Spec didn't forbid this; the four-way duplication exceeded the threshold worth deduping. Surfaced by the `/simplify` reuse agent. |
| `savedChunkFor(phrase)` is a `chunks.data?.find(...)` linear scan recomputed per render (per §How.8 code sample) | `useMemo`'d `Map<normalized-phrase, Chunk>` keyed by `[chunksQuery.data, youtubeId]`; `savedChunkFor` is `map.get(normalizePhrase(phrase))` | O(N) per render with a normalize() call per chunk became O(1) per render; only re-builds on cache invalidation. Surfaced by the `/simplify` efficiency agent. |
| `aria-label="Grabar respuesta (temporal · ver 021)"` and `title="Disponible con 021"` (per §How.5 / §How.6 code samples) | `aria-label="Grabar respuesta (próximamente)"` and `title="Próximamente"` | Internal feature numbers shouldn't leak into user-visible tooltips or a11y tree. Surfaced by the `/simplify` quality agent. |
| `onToggleSavedPhrase` calls `deleteChunkMutation.reset(); saveChunkMutation.reset();` inside both the if and else branches (per §How.8 prose) | `.reset()` calls hoisted above the if/else | Identical behavior, less duplication. |
| AutopsyPanel `error=` prop receives a nested ternary inline in JSX | Nested ternary hoisted to `const saveChunkError = …` above the return | Readability. |
| `ChunkCard.tsx` wraps the phrase `<h3>` in an extra `<div>` (per §How.5 code sample) | Inner `<div>` removed; `<h3>` sits directly under `.chunk-h` | The inner div added no layout value; `.chunk-h` is a flex container, the `<h3>` and `.mastery` are the two intended flex children. |

All other acceptance criteria implemented per spec. Twelve manual-verification steps from spec §How.14 documented and walkthrough-ready (the user runs them against `make dev` + seeded data).

---

## Spec Gaps Exposed

1. **Rail badge wiring was not in the spec's acceptance criteria.** The spec enumerates wiring Inicio's KPI but never mentions the Rail's chunks badge, even though `Rail.tsx` carried a `// Real count comes with feature 020` comment that pre-committed the wiring. Step 4 of the plan folded it in. Future specs should treat such pre-staged TODOs as implicit acceptance criteria or call them out explicitly.

2. **The shared `api()` wrapper's 204 handling was a latent bug, not just a 020 concern.** Spec §Confidence flagged it as a validation item; in practice every existing caller returns JSON and would have survived a future 204-returning endpoint indefinitely. Now fixed proactively. No follow-up needed.

3. **`disabled` styling on `.btn` wasn't in `shell.css`.** Spec §How.8 said "if `:disabled` styling isn't already styled, add it." It wasn't. Added a one-shot system rule (`.btn:disabled, .btn.is-disabled { opacity: 0.55; cursor: not-allowed; }`) rather than scoping to autopsy. Worth a note for future PRs that introduce disabled buttons — the rule already exists.

4. **`normalize_phrase` divergence between casefold (Python) and `toLocaleLowerCase("es")` (JS).** Spec §Open Question §5 framed the contract as "whitespace + casefold." JS has no native casefold. Equivalent for Spanish Whisper output, divergent on edge cases. Decision is to document the divergence honestly in the JS comment rather than implement a casefold polyfill — Whisper never emits ß or final sigma in Spanish dialect output, so the practical risk is zero. If a future feature pipes German or Greek through this normalize, the lookup will silently miss; revisit then.

No spec revisions warranted. No new roadmap items surfaced.

---

## Test Evidence

### Quality gates (lint / typecheck / build)

```
> webapp@ lint /Users/adrianmoses/Developer/comprende-ya/webapp
> biome check

Checked 29 files in 59ms. No fixes applied.
---

> webapp@ typecheck /Users/adrianmoses/Developer/comprende-ya/webapp
> tsc --noEmit

---
dist/client/assets/styles-BJkEmxNC.css      21.31 kB │ gzip:  4.58 kB
dist/client/assets/formatting-B5deQAIu.js    0.12 kB │ gzip:  0.12 kB
dist/client/assets/chunks-DUBm9a_t.js        4.55 kB │ gzip:  1.65 kB
dist/client/assets/routes-CkrKWrHa.js        7.67 kB │ gzip:  2.67 kB
dist/client/assets/listen._id-krDhXLAT.js   17.37 kB │ gzip:  5.66 kB
dist/client/assets/api-HZIq98_A.js          59.84 kB │ gzip: 20.23 kB
dist/client/assets/index-CxYczd_x.js       297.38 kB │ gzip: 93.34 kB

✓ built in 554ms

dist/server/assets/__23tanstack-start-plugin-adapters-y_fshQDY.js    0.18 kB │ gzip:  0.13 kB
dist/server/assets/formatting-DfdssTWF.js                            0.24 kB │ gzip:  0.18 kB
dist/server/assets/start-DfnJ1ivn.js                                 0.28 kB │ gzip:  0.20 kB
dist/server/assets/listen._id-B5ScWs44.js                            0.54 kB │ gzip:  0.33 kB
dist/server/assets/_tanstack-start-manifest_v-DBFqCoeq.js            1.07 kB │ gzip:  0.40 kB
dist/server/assets/api-D9xmivap.js                                   1.66 kB │ gzip:  0.67 kB
dist/server/assets/routes-Do9vaiwo.js                                7.01 kB │ gzip:  1.88 kB
dist/server/assets/chunks-DKA0Kt2Q.js                                7.79 kB │ gzip:  2.23 kB
dist/server/assets/router-DIn98XSq.js                               10.65 kB │ gzip:  2.95 kB
dist/server/assets/listen._id-D0eXxa16.js                           27.11 kB │ gzip:  6.82 kB
dist/server/server.js                                              166.25 kB │ gzip: 41.17 kB

✓ built in 424ms
```

### Backend regression (019 endpoint contract, unchanged by 020)

```
$ uv run pytest tests/test_chunks_routes.py tests/test_chunk_prompts_service.py
…
28 passed, 64 warnings in 8.72s
```

### SSR sanity

`pnpm dev` running; `curl -sS -o /tmp/chunks.html -w "%{http_code}" http://localhost:3000/chunks` →

```
HTTP 200
```

TanStack Start dev-mode SSR manifest in the response body confirms the chunks route matched and rendered server-side without error:

```
matches: [
  { i: "__root__ ", u: 1779015185665, s: "success", ssr: !0 },
  { i: " chunks chunks", u: 1779015185732, s: "success", ssr: !0 }
]
```

(Dev mode hydrates client-side rather than emitting the full DOM as static HTML — the success status + `ssr:!0` on the route match is the relevant signal that no `window`/`document` access errored during SSR. Production-mode SSR-curl with rendered HTML body is part of the 12-step manual smoke when run against `make dev` + seeded data.)

### Manual end-to-end smoke

The 12 verification steps in spec §How.14 are the end-to-end bar and require a running stack + seeded data + browser interaction. They are documented in the spec and are the user's pre-merge walkthrough; outcomes will be noted in the PR description rather than re-listed here.
