# Decision: Inicio (library + KPIs)

| Field | Value |
|---|---|
| spec | [spec.md](./spec.md) |
| plan | `~/.claude/plans/please-restore-the-plan-tingly-snowglobe.md` |
| status | implemented |
| created | 2026-05-03 |

---

## What shipped

`/` renders the real Inicio screen inside the existing rail+topbar shell:

- Greeting (`Buenos días, Ana.`) with a subline that swaps based on whether there's a video to continue.
- KPI grid — `Esta semana` / `Frases guardadas` / `Racha` / `Comprensión`. Three render `—` with the `.kpi-pending` muted style; `Frases guardadas` shows `0` (genuinely zero until 020).
- `Continúa escuchando` — up to 3 videos with `0 < progress < 1`, sorted by most-recent `answered_at` from the progress endpoint, hidden entirely when none match.
- `Tu biblioteca` — every video as a clickable card linking to `/listen/$id`. Each card renders a deterministic OKLCH thumbnail (hue from `video_id` charcode sum), `MM:SS` duration, and an MCQ-derived progress bar.
- Loading: 3-card skeleton (greyscale, lower opacity).
- Error: inline message + `Reintentar` button calling `videosQuery.refetch()`.
- Empty: dashed-border centred message ("Aún no has procesado ningún episodio").

Data layer: `@tanstack/react-query` 5.100.9. `QueryClient` hoisted to module scope in `__root.tsx` (single shared instance, `staleTime: 30_000`). One `useQuery` for the videos list and a single `useQueries` block for per-video progress, with `enabled: !!videosQuery.data` so progress requests don't fire until the list resolves.

## Toolchain

| Choice | Landed | Rationale |
|---|---|---|
| Data layer | **`@tanstack/react-query` 5.100.9** | Spec resolved this open question. Single shared `QueryClient`, no devtools (deferred — the TanStack Router devtools panel covers most needs). |
| Cache window | **`staleTime: 30_000`** | Short enough to feel fresh on revisit, long enough that re-entering Inicio from `/listen/$id` doesn't refetch. |
| Per-video fetch | **`useQueries` (parallel)** | Stable hook count across renders; spec called out an aggregated endpoint as out-of-scope. |
| Card link | **`<Link to="/listen/$id" params={{ id: video.video_id }}>`** | Confirmed the typed-params form works against the existing `routes/listen.$id.tsx`. The rail's `/listen/mercados` string-literal form coexists fine; the typed form is what we want from data-driven Cards. |

## Deviations from spec

1. **`Card` is rendered as a `<Link>` with `cursor: pointer`**, not the design's `cursor: default`. The design CSS leaves cards passive; ours are clickable, so the cursor signals affordance. Tiny but worth noting if a future spec ports the rest of the design's CSS verbatim.
2. **Skeleton card style added inline.** The design bundle has no skeleton state; we added `.card.is-skeleton` rules (lower opacity + greyscale block fills) to `inicio.css`. Three cards, fixed shape, no animation.
3. **Spec referenced an `AnswerProgressRow.selected_answer` field.** The actual backend response uses `user_answer` (verified at `src/api/routes/videos.py:439`). Types in `webapp/src/lib/api-types.ts` use `user_answer`.
4. **Spec referenced `getVideoProgress(videoId: number)`** taking a DB id. The backend's `/videos/{video_id}/progress` route accepts the YouTube id (string). Types and the function signature use `string`.
5. **`VideoProgressResponse.video_id` is `string`** (the YouTube id), not `number` as the spec sketched. Backend wraps the response with `{"video_id": video_id, …}` where `video_id` is the raw YouTube path param.
6. **`questions` field in `VideoListItem` was typed as `number`** in `api-types.ts` from 013 — the actual response embeds full question objects. Fixed to `Array<VideoQuestion>` with the fields Inicio touches (`id`, `correct_answer`, `timestamp`, `answers`, `explanation`). Only consumer was `routes/index.tsx`, so no breakage elsewhere.

## Implementation notes

- **`useQueries` aggregate-pending behaviour matched expectations.** `progressQueries.every((q) => !q.isPending)` is true once every query has data (or has errored). The library grid shows cards at zero-progress as soon as `videosQuery` resolves; "Continúa escuchando" waits for the aggregate, so it doesn't flicker into existence on each per-video resolution.
- **Edge case — zero questions.** `total === 0 ? 0 : answered / total` guards the divide-by-zero. A video with no questions correctly shows `progress = 0` and is excluded from "Continúa escuchando".
- **Edge case — empty progress array.** `lastAnswered` is `null` when no rows; sort treats nulls as `0` (oldest), so videos that are mid-progress with the most-recent activity bubble to the top.
- **Edge case — answered ≥ total.** `Math.min(answered / total, 1)` clamps so a stale-question delete doesn't render a >100% bar.
- **OKLCH hash-color formula (`oklch(0.78 0.06 ${hue})`)** produces pleasantly muted thumbnails. The chroma stays at 0.06 — high enough to differentiate, low enough to not fight the page's restraint. No tuning needed.

## Final verification

- `pnpm lint` — clean (Biome 2.4.5; one pass needed `pnpm format` to canonicalise; one CSS specificity warning resolved by reordering `.card.is-skeleton` rules below `.card-title`).
- `pnpm typecheck` — clean (TypeScript 6, strict).
- `pnpm build` — clean (client + SSR bundles).
- Manual verification deferred to user run; covered by the plan's Phase 6 checklist.

## Open follow-ups (none blocking)

- **Real KPI values** land with item 022. The `.kpi-pending` modifier signals the wiring is intentional.
- **`Frases guardadas` count** lights up with item 020 (chunk library).
- **Search bar in TopBar** stays a no-op until a future search/process-new-video spec.
- **Pagination** of the library grid lands when count grows past `limit=20`.
- **"hace 2 horas" section meta** on `Continúa escuchando` waits for 022's activity timestamp.
- **Devtools** for react-query intentionally skipped; cheap to add when caching pain shows up.
