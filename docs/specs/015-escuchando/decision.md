# Decision: Escuchando (video, scrubber, transcript, MCQ rail)

| Field | Value |
|---|---|
| spec | [spec.md](./spec.md) |
| plan | `~/.claude/plans/please-restore-the-plan-tingly-snowglobe.md` |
| status | implemented |
| created | 2026-05-03 |

---

## What shipped

`/listen/$id` renders the real Escuchando screen inside the rail+topbar shell:

- **Player.** Real YouTube IFrame API embed via `useYouTubePlayer`. Native YouTube controls hidden (`controls: 0`); the design's central play overlay is the sole transport surface alongside the custom scrubber.
- **Scrubber.** Click-to-seek. One vertical mark per question's timestamp.
- **Transport.** ±5s skip, speed cycle (1× → 0.85× → 0.7× → 1.25× → 1×), legend.
- **Transcript.** Plain segment text from `GET /api/videos/{db_id}/segments`. `is-current` highlight tracks `currentTime` from a 250 ms `setInterval` while playing.
- **MCQ auto-pause.** A single `useEffect` finds the first unanswered question whose `timestamp ≤ currentTime` and not in the progress map, sets `pendingQuestionId`, pauses the player, and `seekTo`s the question's timestamp. Latch: the effect's first branch `if (pendingQuestionId !== null) return` prevents re-fire while a panel is open.
- **QuestionPanel.** Four lettered choices. `is-correct` (correct) and `is-wrong` (the chosen wrong option) styling. Explanation reveal. `Seguir →` resumes play. `correct_answer` is in the question payload, so we don't wait on the mutation to render the answered state.
- **SessionPanel.** Always visible. Tag `${answered}/${total} preguntas`. Per-question row: index circle + appearance time, or ✓/× circle + "Respondida" once answered.
- **Skeleton / ErrorState / NotFound.** All rendered. NotFound triggered by `Error("404 …")` from the existing `api()` wrapper. NotFound + ErrorState retries are gated so 404s don't retry.

Data layer (first uses of `useMutation` and `useQueryClient` in the project):

```ts
const mutation = useMutation({
  mutationFn: ({ questionId, userAnswer }) => saveProgress(youtubeId, questionId, userAnswer),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ["video-progress", youtubeId] }),
});
```

Three queries: `['video', youtubeId]`, `['video-segments', dbId]` (chained via `enabled: !!videoQuery.data`), `['video-progress', youtubeId]` (parallel with video). Narrow invalidation key matches Inicio's `useQueries` keys exactly, so back-navigate updates the progress bar without refetch flash.

## Toolchain

| Choice | Landed | Rationale |
|---|---|---|
| Player API | **YouTube IFrame API** | We don't host audio. Direct script tag, no npm wrapper. SSR-safe by deferring all `window`/`document` access into `useEffect`. |
| Types | **`@types/youtube` 0.2.0** | Solves Biome's `noExplicitAny` complaint. Required adding `"youtube"` to `tsconfig.json`'s `types` array. |
| Tick cadence | **`setInterval(250)`** | Matches the design prototype. `requestAnimationFrame` would be smoother but unnecessary at the design's bar resolution. |
| MCQ trigger | **`question.timestamp` directly** | Simpler than the design's segment-bound dance. Real backend timestamp is the segment-aligned point Whisper returned. |
| Speaker label | **Static `Narrador/a`** | Whisper segments don't carry diarisation; placeholder until/unless that lands. |
| Channel name | **Static `—`** | Backend doesn't store channel; same shape as 014's `.kpi-pending` muting. |

## Deviations from spec & plan

1. **`Window` type augmentation moved to a separate `.d.ts` file.** The plan put `declare global { interface Window { YT?: typeof YT; ... } }` inside the hook module. TypeScript flagged `'YT' refers to a UMD global, but the current file is a module` (TS2686) — UMD globals can't be referenced in `typeof` position from inside a module. Fix: move the augmentation to `webapp/src/types/youtube-window.d.ts` (a script file, no imports/exports = no UMD-in-module clash). Hook now references `window.YT?.Player` etc. with full typing intact, no `any`.

2. **`segmentsQuery.queryFn` uses an explicit guard, not a non-null assertion.** Plan implied `getVideoSegments(videoQuery.data!.id)`. Biome's `noNonNullAssertion` warns on this. Replaced with `if (!videoQuery.data) throw …; return getVideoSegments(videoQuery.data.id);` — same behaviour, no `!`. The `enabled: !!videoQuery.data` flag means the throw branch is unreachable in practice.

3. **Choice key uses `text` not `idx`.** Biome's `useNoArrayIndexKey` rule. MCQ answers within a question are unique by construction.

4. **Skeleton + 404 + Error states render the full route** (replace the entire main column), not just the right side. The design didn't specify these states, and replacing the whole content felt cleaner than leaving the rail/main scaffolding around an empty error block.

5. **`formatDuration` duplicated, not lifted.** Plan flagged "lift to `webapp/src/lib/format.ts` if it'd benefit other screens." Decided against — only two callers (Inicio + Escuchando), trivial to keep in sync, lifting now would be premature.

## Implementation notes

- **SSR sanity (verified via `curl http://localhost:3001/listen/m1DFpkNdcv0`).** Server returns the rail / topbar / Skeleton state with no errors. Queries don't run server-side (no SSR-query hydration setup), so the Skeleton is what hydrates from. No hydration warning on the client. The `yt-player` div is only present after the queries resolve — the iframe mounts purely client-side.
- **`isPlaying` source of truth.** The hook updates internal state from YouTube's `onStateChange` event, never optimistically. So if the user pauses via YouTube's keyboard shortcut or via the MCQ-due effect's `pause()` call, the UI's play-button overlay flips to "playing" → "paused" cleanly.
- **MCQ-due latch behaviour.** The `pendingQuestionId !== null` first-branch return in the effect handles the moment between `setPendingQuestionId` and the player actually pausing — the effect could re-fire from a `currentTime` tick, but the latch holds.
- **`setPlaybackRate` before `isReady`.** Hook action functions are no-ops while `playerRef.current` is null. Speed clicks during the ~100ms script-load window do nothing (no error, no queue). Acceptable.
- **404 detection.** The existing `api()` wrapper throws `Error("404 Not Found")` (or whatever statusText returned). `isNotFoundError(error)` checks `error.message.startsWith("404")`. Also disables retries on 404 so `NotFound` renders immediately, not after three retries.

## Final verification

- `pnpm lint` — clean (Biome 2.4.5; one autoformat pass needed).
- `pnpm typecheck` — clean (TypeScript 6, strict).
- `pnpm build` — clean (client + SSR bundles).
- SSR curl — returns 9.3 KB shell with rail / topbar / Skeleton, no errors.
- Manual smoke deferred to user run; covered by the plan's Phase 6 checklist.

## Backend bug surfaced during smoke

`GET /api/videos/{db_id}/segments` raised `TypeError: SegmentsRepository.__init__() missing 1 required positional argument: 'session'` on every call. Two bugs at `src/api/routes/videos.py:301-304`:

1. `SegmentsRepository()` constructed without its required `session` argument.
2. `extract_and_save_segments(video, session)` passed an extra `session` arg — the method's signature only takes `video` and uses `self.session` internally.

Compounding: the repo was constructed unconditionally before the lazy-extract branch, so even videos with already-materialised segments (the common case) hit the error.

Fixed in this PR by moving the repo construction inside the `if not segments and video.full_transcript_data:` branch, passing `session` correctly, and dropping the extra arg from the method call. No backend tests covered this route; existing test suite (17 tests) still passes; ruff clean. The flow's own use of `SegmentsRepository(db)` at `src/flows/video_processing.py:107,117` is correct and unchanged.

## Open follow-ups (none blocking)

- **`/segments` route still takes int DB id.** Spec §Open Q1 noted this as a backend wart. Worked around on the frontend (chained queries). A small backend cleanup spec can normalise the endpoints later.
- **No transcript auto-scroll.** First-cut omission. If the active segment regularly leaves the viewport during manual smoke, revisit.
- **Cascading question fire** (if user seeks past multiple unanswered questions, they fire in sequence as each is answered). Current behaviour, matches the design prototype's logic. Acceptable.
- **016 (Phrase Autopsy panel)** drops a panel into the existing `aside` container — no rail-layout changes needed.
- **020 (Mis frases)** depends on 016's autopsy panel (where the save action lives) plus this screen's progress writes (already shipping).
