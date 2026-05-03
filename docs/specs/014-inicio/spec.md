# Spec: Inicio (library + KPIs)

| Field | Value |
|---|---|
| id | 014 |
| status | approved |
| created | 2026-05-03 |

---

## Why

Inicio is the first thing Ana sees when she opens the app. Today it's a placeholder. Until it shows real content — her library of episodes, what she was last working on, and how she's doing — there's no path from "open app" to "study Spanish." Every other frontend feature (015 Escuchando, 016 Phrase Autopsy, 020 Mis frases) assumes the user got to it from a card on Inicio.

This spec ships the Inicio chrome from the design — page header, KPI grid, "Continúa escuchando" carousel, "Tu biblioteca" grid — wired to the data the backend has today (`GET /api/videos/`, `GET /api/videos/{id}/progress`). KPI values that depend on yet-to-build backends (streak, week minutes, comprehension %) render as visible placeholders with `—`; they light up when item 022 lands. Progress per episode is derived from MCQ-answer ratio (a proxy for true playback position, which the backend doesn't track).

### Consumer Impact

- **Ana**, the single B2 learner. She opens `localhost:3000`, sees her real library, sees which episode she was in the middle of, and clicks a card to enter Escuchando. The feedback loop is closed for the first time.
- **Future feature specs (015, 020).** They get a real entry point. Card-click navigation to `/listen/$id` becomes the canonical pattern, not a placeholder.
- **The audit/decision trail.** Inicio is the first screen with real data fetching, so it's where the frontend's data-fetching pattern (TanStack Query vs. ad-hoc `useEffect`) gets locked in for everyone after it.

### Roadmap Fit

- **Depends on:** 013 (frontend shell, shipped). The rail's "Inicio" link, the topbar crumbs, the theme tokens, the API client, and the placeholder route are already in place — this spec replaces only the placeholder body.
- **Unblocks:** 015 (Escuchando) — needs a way to navigate to specific videos. 020 (Mis frases) — needs the `Frases guardadas` KPI to start surfacing real numbers when chunks land.
- **Doesn't block:** any backend item. Inicio's KPIs degrade gracefully to `—` until 022 ships; the rest of Inicio runs against existing endpoints.

---

## What

### Acceptance Criteria

- [ ] Visiting `/` renders the Inicio screen inside the existing rail+topbar shell. No placeholder copy remains.
- [ ] The page renders four sections in order: greeting header → KPI grid (4 cards) → "Continúa escuchando" (when applicable) → "Tu biblioteca".
- [ ] **Library grid** lists every video returned by `GET /api/videos/` as a clickable card. Cards show: generated thumbnail (deterministic color from `video_id` hash), duration formatted as `MM:SS`, title, and an MCQ-progress bar overlaid on the thumbnail.
- [ ] Card click navigates to `/listen/$video_id` (YouTube id). Browser back/forward works.
- [ ] **"Continúa escuchando"** shows up to 3 videos with `0 < mcq_progress < 1`, sorted by most-recent activity. The section is hidden entirely when no video matches.
- [ ] **KPI grid** renders four cards: `Esta semana`, `Frases guardadas`, `Racha`, `Comprensión`. Each card uses the design's typography (label uppercase, value in `Instrument Serif`, optional unit suffix). Until 022 lands, all four values are static placeholders (`—` or `0`); a small `kpi-pending` annotation signals the wiring is intentional, not broken.
- [ ] **MCQ progress** per video is derived as `answered_count / question_count`. If a video has zero questions, progress is `0`. Computed by calling `GET /api/videos/{id}/progress` once per video, in parallel.
- [ ] **Empty state** — when `GET /api/videos/` returns `{ videos: [] }`, the library grid is replaced by a centered message ("Aún no has procesado ningún episodio") and no "Continúa escuchando" section. KPI grid still renders.
- [ ] **Loading state** — initial fetch shows a low-contrast skeleton for the library grid. Greeting and KPI grid are visible immediately (they don't depend on the fetch).
- [ ] **Error state** — if `GET /api/videos/` fails, the library grid is replaced by an inline error message with a "Reintentar" button that re-runs the query.
- [ ] All copy is Spanish.
- [ ] `pnpm lint`, `pnpm typecheck`, `pnpm build` are clean.

### Non-Goals

- **Real KPI values.** All four KPIs are placeholders. Wiring streak / week minutes / comprehension % to real data is item 022. `Frases guardadas` lights up after 020.
- **Time-of-day greeting.** "Buenos días, Ana" stays static. No "buenas tardes/noches" branching in this spec.
- **Channel name or level tag on cards.** Backend doesn't store either. Cards omit them; design's `B2` and `Voces de la ciudad` placeholders are dropped, not faked.
- **Pattern-based thumbnails.** The design has six SVG patterns (`a` through `f`). We render solid color only — derived from `video_id`. Patterns can land in a follow-up spec.
- **YouTube thumbnails.** Available via the YouTube Data API but not stored. Generated colors keep the page lean and consistent with the OS-native design language.
- **Search bar functionality.** TopBar's "Buscar episodios" button stays a no-op (it's part of a future search/process-new-video spec).
- **Real "last activity" timestamp** ("hace 2 horas" in the design's section meta). Hidden until 022 supplies it.
- **Pagination of the library grid.** `GET /api/videos/?skip=&limit=` exists but the library is small enough today (single digits) that we fetch the default `limit=20` and call it done. Pagination lands when count grows.
- **A new aggregated `/api/progress/summary` endpoint.** Calling `GET /api/videos/{id}/progress` per video in parallel is fine at single-digit counts; backend optimization can come if it bites.
- **Frontend tests.** Same deferral as 013 — manual smoke is the bar. A separate frontend-test-infra spec will land before the screen count gets unmanageable.

### Open Questions

1. **Add TanStack Query?** Recommendation: **yes.** `@tanstack/react-query` pairs naturally with the TanStack Router we already ship; gives caching across route navigation, loading/error states for free, and avoids a hand-rolled `useEffect`+`useState` dance per data screen. Inicio is the first screen with two coordinated fetches (`listVideos()` + N parallel `getProgress(id)`); doing this without Query writes more code than installing it. Cost: one dep, one provider mounted in `__root.tsx`. Resolved in `decision.md`.
2. **MCQ progress as proxy for episode progress.** The design's "Continúa escuchando" filter is `progress > 0 && progress < 1`. We don't have playback position. MCQ-answered ratio is the closest existing signal. Honest enough — if Ana answered some MCQs but not all, she's mid-episode. Backed by `AnswerProgress` rows. Note in `decision.md` that this is a proxy.
3. **Card destination — YouTube id or DB id?** Use `video_id` (the YouTube id). The rail's existing "Escuchando ahora" link points to `/listen/mercados` — by-name, public-ID convention. The DB `id` is an internal detail; URLs should not depend on it.
4. **Color hash function.** Simple: `Array.from(video_id).reduce((a, c) => a + c.charCodeAt(0), 0) % 360` → HSL hue. `oklch(0.78 0.06 ${hue})`. Deterministic, ten lines of code, no extra dep. Resolved.
5. **Should KPI placeholder values be `0` or `—`?** Recommendation: **`—`** for `Esta semana`, `Racha`, `Comprensión` (they are unknown, not zero); **`0`** for `Frases guardadas` (the chunk library is empty, which is genuinely zero). The visual difference between "unknown" and "literally zero" matters for the "wiring's intentional, not broken" signal.

---

## How

### Approach

#### 1. Data layer

**Add `@tanstack/react-query` (latest 5.x).** Wrap the app in `<QueryClientProvider>` inside `__root.tsx`'s `RootLayout`. Single shared `QueryClient` instance hoisted to module scope.

Extend `webapp/src/lib/api.ts` with two new functions and types:

```ts
// existing
export function listVideos(): Promise<VideoListResponse>;

// new
export type AnswerProgressRow = {
  question_id: number;
  selected_answer: number;
  is_correct: boolean;
  answered_at: string;
};
export type VideoProgressResponse = {
  video_id: number;
  progress: Array<AnswerProgressRow>;
};
export function getVideoProgress(videoId: number): Promise<VideoProgressResponse>;
```

The route shape for `/{video_id}/progress` lives in `src/api/routes/videos.py:415`. Confirm fields during implementation; types here are best-effort from reading.

#### 2. Inicio route body

Replace `webapp/src/routes/index.tsx` with a real component:

```tsx
function Inicio() {
  const videosQuery = useQuery({
    queryKey: ['videos'],
    queryFn: () => listVideos(),
  });
  const progressQueries = useQueries({
    queries: (videosQuery.data?.videos ?? []).map((v) => ({
      queryKey: ['video-progress', v.id],
      queryFn: () => getVideoProgress(v.id),
      enabled: !!videosQuery.data,
    })),
  });
  // derive { id → progress } map and continueListening list
  // render: <Greeting/> <KpiGrid/> <ContinueListening/> <Library/>
}
```

Components live as named exports inside `routes/index.tsx` for now — small enough not to extract until they're reused. If any one passes ~50 lines, lift to `webapp/src/components/inicio/`.

#### 3. Card thumbnail

Inline component, same file. Renders an `<a>` (Link) wrapping:

```tsx
<div className="thumb" style={{ background: hashColor(video.video_id) }}>
  <span className="thumb-dur">{formatDuration(video.duration)}</span>
  <div className="thumb-progress"><span style={{ width: `${pct * 100}%` }} /></div>
</div>
<div className="card-body">
  <div className="card-title">{video.title}</div>
</div>
```

`hashColor` and `formatDuration` are 5-line pure helpers in the same file.

#### 4. Styles

Port the home-relevant CSS from `docs/artefacts/project/styles.css:204-347` into a new `webapp/src/styles/inicio.css`:

- `.page`, `.page-h`, `.page-sub`
- `.kpis`, `.kpi`, `.kpi-label`, `.kpi-val`, `.kpi-val small`
- `.section-title`, `.section-title .meta`
- `.lib-grid`, `.card`, `.card:hover`, `.card-body`, `.card-title`
- `.thumb`, `.thumb-dur`, `.thumb-progress`, `.thumb-progress span`

Drop styles we're not using yet: `.thumb-stripes`, `.thumb-label`, `.tag`, `.tag.level`, `.card-meta`. They land with their respective features.

Add `@import "./styles/inicio.css";` to `webapp/src/styles.css`.

Add a small `.kpi-pending` rule (lower-opacity value) to make the placeholder state visually distinguishable without being hostile.

#### 5. Empty / loading / error states

- **Empty:** `videosQuery.data.videos.length === 0` → render a centered `<div className="page">` with a single message. No KPI changes — the grid renders with placeholders as usual.
- **Loading:** while `videosQuery.isPending`, render the library grid with three skeleton cards (matching `.card` shape, lower opacity, no content). The KPI grid + greeting render immediately because they don't depend on the fetch.
- **Error:** `videosQuery.isError` → inline error message + `<button onClick={() => videosQuery.refetch()}>Reintentar</button>`. KPIs still render.

#### 6. Verification

Same manual-smoke bar as 013:

1. Backend up (`uv run ... fastapi run ... --host ::`), frontend up (`pnpm dev`), open `http://localhost:3000/`.
2. Confirm: greeting + KPI grid (with placeholders) + library grid render; cards have unique colors; durations formatted as `MM:SS`; clicking any card navigates to `/listen/$youtube_id` and the rail's "Escuchando ahora" goes active.
3. With at least one MCQ answered on a video (existing seed data), confirm "Continúa escuchando" appears with that video and the progress bar reflects the ratio.
4. Stop the backend mid-load; refresh; confirm error state + Reintentar button. Restart backend, click Reintentar, confirm recovery.
5. With an empty DB (no seed data), confirm empty-state copy renders.

### Confidence

**Level:** High

**Rationale:**

- Backend endpoints exist and are well-typed. `GET /api/videos/` and `GET /api/videos/{id}/progress` are both implemented (008, 009).
- The shell, theme tokens, API client, and route are all in place from 013. This spec replaces a route body and adds three CSS sections — no new toolchain or framework decisions.
- TanStack Query is a well-trodden library, and the route-level integration is straightforward.
- Generated thumbnails (color hash) are five lines of code and have no failure modes.
- All states (loading, empty, error) have clear acceptance criteria and obvious implementations.

The only judgment call is the MCQ-progress proxy, which is documented and intentionally approximate.

### Key Decisions

- **Add TanStack Query.** Worth one dep; pays off at every screen after this. The 013 deferral ("add a store when a screen needs it") triggered now, on the first multi-fetch screen.
- **Generated thumbnails over YouTube thumbnails.** Cheaper payload, consistent OS-native aesthetic, no extra fetch dance, no risk of broken images. Pattern overlay is a follow-up.
- **MCQ-answered ratio as the "progress" signal.** Best available proxy; documented as such. Real playback position is a backend concern that doesn't yet have a roadmap entry.
- **Per-video progress fetch in parallel via `useQueries`** instead of an aggregated endpoint. Acceptable at current library size; revisit when count grows.
- **No state library beyond Query.** URL state via the router; query state via Query; component state via `useState`. No Zustand/Jotai/Redux.

### Testing Approach

Same as 013: manual smoke is the bar. Frontend automated test infra is its own future spec. After implementation:

- `pnpm lint` clean
- `pnpm typecheck` clean
- `pnpm build` clean (client + SSR bundles)
- The five manual-verification steps from §6 above
- A short note in `decision.md` recording any deviations and the actual TanStack Query version installed
