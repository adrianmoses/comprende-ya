# Spec: Escuchando (video, scrubber, transcript, MCQ rail)

| Field | Value |
|---|---|
| id | 015 |
| status | approved |
| created | 2026-05-03 |

---

## Why

Inicio (014) closes the loop from "open app" to "pick a video," but tapping a card lands on a placeholder. Escuchando is where the actual studying happens — Ana plays the video, sees the transcript scroll under it, gets paused at a comprehension MCQ when one is due, answers it, and continues. Without this screen the backend's transcript + MCQs sit unused; with it, the daily-use loop is real.

The design splits the right rail across three concerns: comprehension MCQs (this spec), Phrase Autopsy (016), and saved-phrase confirmation (020). This spec ships only the MCQ side. The aside structure is built so 016 and 020 can drop in without restructuring it.

### Consumer Impact

- **Ana**, the single B2 learner. She clicks an Inicio card, the Escuchando view opens, the YouTube video plays, the transcript follows along, a question appears at its timestamp, she answers, the explanation lands, she continues. This is the first time the product delivers on its core job-to-be-done.
- **Future feature specs.** 016 (Phrase Autopsy panel) drops a second panel into the right rail — needs the rail layout to exist. 020 (Mis frases) needs the save-phrase action wired into the rail's autopsy panel — also depends on 016, but the rail container ships here.
- **Backend MCQ progress (009).** Currently exercised only by Inicio's progress-bar derivation. This is the screen that actually writes new rows.

### Roadmap Fit

- **Depends on:** 013 (frontend shell — rail / topbar / theme), 014 (Inicio — query provider, API client patterns, the cards that link here).
- **Unblocks:** 016 (Phrase Autopsy panel — fits inside the rail this spec builds), 020 (Mis frases — depends on the save-phrase action which lives in 016's autopsy panel, but Mis frases also reads progress this screen writes).
- **Doesn't block:** any backend item. All endpoints exist (008 video CRUD, 009 progress save). Token-level transcript (018) and Phrase Autopsy data (017) only matter when 016 lands — the transcript here is plain segment text.

---

## What

### Acceptance Criteria

- [ ] Visiting `/listen/$id` (where `$id` is a YouTube id) renders the Escuchando screen inside the existing rail+topbar shell.
- [ ] **Video player.** Embeds the actual YouTube video via the YouTube IFrame API. Play/pause via the central play-button overlay; clicking the play button toggles state. The video metadata title and channel render in the bottom overlay (channel = static "—" placeholder until backend stores it; see Open Questions).
- [ ] **Scrubber.** A horizontal bar showing playback position as a fraction of total duration. Click anywhere on the bar to seek the player to that timestamp. The scrubber renders a vertical mark at every question's timestamp.
- [ ] **Transport row.** Three controls: ±5s skip buttons that seek relative, and a speed cycle (`1×` → `0.85×` → `0.7×` → `1.25×` → `1×`) that calls `setPlaybackRate` on the player. A right-aligned legend reads "Pregunta de comprensión" next to a sample mark.
- [ ] **Transcript.** Renders all segments from `GET /api/videos/{db_id}/segments` in chronological order. Each segment shows speaker (placeholder until backend tracks it — render `Narrador/a`), `MM:SS` start time, and the segment text. The segment whose `start_time ≤ currentTime < end_time` gets the `is-current` background; transitions ride the player's `onStateChange` / a polled `getCurrentTime`.
- [ ] **MCQ auto-pause.** When playback crosses a question's timestamp (or the end of the segment that contains it), the player pauses, the right rail surfaces a `QuestionPanel` for that question, and the time snaps to the question's timestamp. Already-answered questions don't re-fire.
- [ ] **MCQ panel.** Shows the prompt, four lettered choices (A–D), and on click: highlights correct (green) and the wrong choice (red, when wrong), reveals an explanation, and shows a `Seguir` button that resumes playback and clears the panel. Calls `POST /api/videos/{youtube_id}/progress` with `question_id` and `user_answer` once per question.
- [ ] **Session panel.** Always visible below the active panel. Shows N/M progress (N answered / M total), and a list-row per question with a status circle (gray = unanswered + appearance time, green ✓ = correct, red × = wrong). Driven by the same answered-state used by the MCQ panel.
- [ ] **Empty / loading / error states.** Loading: a low-contrast skeleton for the video frame + transcript while either query is pending. Error: inline `Reintentar`. Missing video (404): centered message + "Volver a Inicio" link.
- [ ] **Navigating back to Inicio** preserves no in-screen state (player resets); but the question-progress writes from this session are visible immediately on Inicio's progress bars (cache invalidation on the right keys).
- [ ] All copy is Spanish.
- [ ] `pnpm lint` / `typecheck` / `build` clean.

### Non-Goals

- **Phrase Autopsy panel and tappable interesting words** (item 016). Transcript renders as plain text — no token-level annotations, no underlined phrases, no autopsy fetch. The aside layout is built to accept a second panel, but only the MCQ + Session panels render here.
- **Save phrase to library** (items 019/020). No bookmark icons on words, no save-confirmation panel.
- **"+ Inglés" literal toggle.** Per OVERVIEW.md §Non-Goals, the product has no English translations or glosses anywhere — the toggle row from the design is dropped permanently, not deferred.
- **Speaker diarisation.** Whisper segments don't carry speaker labels; we render a static `Narrador/a` per segment and revisit when/if the backend supplies speakers.
- **Channel name on the video overlay.** Backend doesn't store channel; render `—` and revisit when 022 or a metadata-extension spec lands.
- **Video-frame thumbnail / pattern overlay.** The actual YouTube iframe replaces the design's synthetic gradient panel; no placeholder gradient, no pattern stripes.
- **Continuous-time scrolling of the transcript** to keep the active segment in view. Out of scope to keep the first cut simple — Ana scrolls the transcript pane manually. Worth reconsidering after manual smoke if it bites.
- **Fill-in-the-blank exercises.** `GET /api/videos/{id}` returns these but the design's listen view never surfaces them. They land with their own future spec (a study-mode review screen, possibly).
- **Keyboard shortcuts** (space = play/pause, arrows = ±5s). Standard player conveniences, but the design doesn't specify them and we keep scope tight.
- **Frontend tests.** Same deferral as 013/014 — manual smoke is the bar until a frontend-test-infra spec lands.

### Open Questions

1. **Backend route mismatch — `/segments` takes int id, video detail takes string YouTube id.** `GET /api/videos/{video_id}` accepts the YouTube id (string); `GET /api/videos/{video_id}/segments` accepts the DB id (int). Two ways to handle: (a) fix the backend to accept the YouTube id consistently (small backend PR before 015), (b) fetch the video first to get its DB id, then fetch segments. Recommendation: **(b) for this spec.** It keeps 015 frontend-only — we already pay one round-trip for the video detail anyway, so the segments fetch becomes `enabled: !!videoQuery.data` and chains. A backend cleanup spec can normalise the endpoints later.

2. **Player choice — YouTube IFrame API vs. plain HTML5 video.** Recommendation: **YouTube IFrame API.** The original audio file is downloaded and discarded by the backend; we have no hosted media to play. The YouTube id we already store points directly at the source. The IFrame API gives us `playVideo()` / `pauseVideo()` / `seekTo()` / `getCurrentTime()` / `setPlaybackRate()` / `onStateChange` — exactly the controls the design needs. Cost: an external script tag (`https://www.youtube.com/iframe_api`), one global callback (`onYouTubeIframeAPIReady`), and a 16:9 wrapper. No npm wrapper needed; a thin `useYouTubePlayer(videoId)` hook handles it.

3. **Time tick cadence.** YouTube's IFrame API doesn't fire a `timeupdate` event. Two options: (a) `requestAnimationFrame` loop while playing (smooth scrubber, costs a frame of work), (b) `setInterval` at 250 ms (cheaper, scrubber moves in 250 ms steps which is fine at the design's bar resolution). Recommendation: **`setInterval(250ms)`**. Matches the design's prototype tick, eyes can't see finer at this scale, easy to pause when the player isn't playing. We already store seconds as a float so seek precision is unaffected.

4. **MCQ trigger — by question timestamp or by end-of-segment?** Backend stores `Question.timestamp` as a float (seconds). The design fires the question at `seg.end` of the segment matching `q.afterSegment`. Recommendation: **trigger at `question.timestamp` directly.** Each question's timestamp from `services/questions.py` is "the timestamp of the segment the question targets" — close enough to the natural pause point. Simpler than the segment-lookup dance and keeps the implementation closer to the data we have. If pauses feel poorly placed in manual smoke, we revisit.

5. **What does `Seguir` do if the user navigates away mid-question?** Recommendation: dismiss the panel on route change (`useEffect` cleanup), don't persist the "pending question" across navigations. The next time they enter the screen, the question fires again only if it hasn't been answered. The `progressQueries` from Inicio already cover the answered state through cache.

6. **Cache invalidation after answering.** When `POST /progress` succeeds, we want Inicio's progress bars to update. Two options: (a) invalidate `['video-progress', youtubeId]` after every mutation (one query refetches), (b) invalidate `['video-progress']` (broad). Recommendation: **(a)** — narrow invalidation, cheap, and the only consumer that cares is Inicio plus this same screen.

---

## How

### Approach

#### 1. Route & data layer

`webapp/src/routes/listen.$id.tsx` already exists as a placeholder from 013. Replace its body with the real component.

Two queries, chained:

```ts
const videoQuery = useQuery({
  queryKey: ['video', youtubeId],
  queryFn: () => getVideo(youtubeId),
});
const segmentsQuery = useQuery({
  queryKey: ['video-segments', videoQuery.data?.id],
  queryFn: () => getVideoSegments(videoQuery.data!.id),
  enabled: !!videoQuery.data,
});
const progressQuery = useQuery({
  queryKey: ['video-progress', youtubeId],
  queryFn: () => getVideoProgress(youtubeId),
});
```

New API functions in `webapp/src/lib/api.ts`:

- `getVideo(youtubeId: string): Promise<VideoDetail>` — `GET /api/videos/${id}`.
- `getVideoSegments(dbId: number): Promise<Array<TranscriptSegment>>` — `GET /api/videos/${id}/segments`.
- `saveProgress(youtubeId: string, questionId: number, userAnswer: number): Promise<ProgressRow>` — `POST /api/videos/${id}/progress?question_id=…&user_answer=…`. Backend uses query params, not a JSON body (per `videos.py:371`).

New types in `webapp/src/lib/api-types.ts`:

```ts
export type VideoDetailQuestion = {
  id: number;
  timestamp: number;
  question: string;
  answers: Array<string>;       // already JSON-parsed by backend
  correct_answer: number;       // 0-3
  explanation: string | null;
};
export type VideoDetail = {
  id: number;
  video_id: string;
  url: string;
  title: string;
  duration: number;
  questions: Array<VideoDetailQuestion>;
  created_at: string;
};
export type TranscriptSegment = {
  segment_number: number;
  transcript: string;
  start_time: number;
  end_time: number;
};
```

The existing `VideoListItem.questions: Array<VideoQuestion>` shape is the *summary* on `/api/videos/`. The detail endpoint returns `answers` already JSON-parsed (`json.loads(q.answers)` in `videos.py:234`). Different shape, separate type.

#### 2. YouTube player

Hook: `webapp/src/hooks/useYouTubePlayer.ts`. Lazy-loads `https://www.youtube.com/iframe_api` once per page life, exposes:

```ts
useYouTubePlayer({
  containerId: string;
  videoId: string;
  onReady?: () => void;
  onStateChange?: (state: PlayerState) => void;
}) → {
  play(): void;
  pause(): void;
  seekTo(seconds: number): void;
  setPlaybackRate(rate: number): void;
  getCurrentTime(): number;
  isReady: boolean;
  isPlaying: boolean;
}
```

The hook owns the `YT.Player` instance, the script-tag bootstrap, and the global `window.onYouTubeIframeAPIReady` queue (so multiple components can coexist).

A 250 ms `setInterval` — wired in the consumer, not the hook — polls `getCurrentTime()` while playing and writes `currentTime` to React state. The interval clears when not playing.

#### 3. Component structure

All inline in `routes/listen.$id.tsx`:

- **`Escuchando`** — top-level. Holds the queries, the `currentTime` state, the `pendingQuestionId` state, and the `playbackRate` state. Computes `currentSegment` from `currentTime` and `segments`. Detects MCQ-due transitions and updates `pendingQuestionId`.
- **`VideoFrame`** — wraps the YouTube iframe in a 16:9 container. Renders the central play button overlay (controlled by `isPlaying`) and the bottom title overlay.
- **`Scrubber`** — receives `currentTime`, `duration`, `questions`, `onSeek`. Renders fill, thumb, and one mark per question.
- **`Transport`** — receives `currentTime`, `playbackRate`, callbacks. Renders ±5s, the speed cycle button, and the legend.
- **`Transcript`** — receives `segments`, `currentSegment`. Renders one `Segment` per row. No tappable words (out of scope per non-goals).
- **`Aside`** — renders a `QuestionPanel` when `pendingQuestionId` is set, otherwise a hint card. Always renders the `SessionPanel` below.
- **`QuestionPanel`** — handles answer click, calls the mutation, and renders correct/wrong/explanation/Seguir flow.
- **`SessionPanel`** — receives `questions` and `progressQuery.data`, renders the row-per-question with status circles.
- **`Skeleton`** / **`ErrorState`** / **`NotFound`** — for loading / error / 404.

Mutation:

```ts
const mutation = useMutation({
  mutationFn: ({ questionId, userAnswer }) => saveProgress(youtubeId, questionId, userAnswer),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['video-progress', youtubeId] });
  },
});
```

#### 4. Styles

Port the listen-relevant CSS from `docs/artefacts/project/styles.css:349-770` into a new `webapp/src/styles/escuchando.css`:

- `.listen`, `.listen.no-aside`
- `.video-wrap`, `.video-canvas` (re-purposed as the iframe wrapper), `.video-overlay`, `.video-title`, `.video-channel`, `.play-btn`, `.play-btn.is-playing`
- `.scrubber`, `.scrubber-time`, `.scrub-bar`, `.scrub-fill`, `.scrub-mark`, `.scrub-thumb`
- `.transport`, `.transport .speed`
- `.transcript`, `.transcript-h h3`, `.segment`, `.segment.is-current`, `.seg-speaker`, `.seg-speaker .ts`, `.seg-text`
- `.aside`, `.panel`, `.panel-h`, `.panel-h h4`, `.panel-h .panel-tag`, `.panel-body`
- `.q-prompt`, `.q-meta`, `.choices`, `.choice`, `.choice .key`, `.choice.is-correct`, `.choice.is-wrong`, `.choice.is-disabled`, `.q-explain`, `.q-foot`
- `.aside-empty`

Skip permanently (no English in the product): `.toggle-row`. Skip deferred to 016/020: `.seg-text .word` and `.is-saved`/`.is-active` variants (no tappable words yet), `.autopsy-*`, `.layer-*`, `.gram-*`, `.nat-row`.

Add `@import "./styles/escuchando.css";` to `webapp/src/styles.css` after `inicio.css`.

#### 5. Verification

Manual smoke against the existing seed data (videos `m1DFpkNdcv0`, `mJsPFDkv0Vk`):

1. Backend up (`uv run … fastapi run … --host ::`), frontend up (`pnpm dev`).
2. Open `http://localhost:3000/`, click any card with seeded MCQ progress (Inicio shows progress bars).
3. URL is `/listen/$id`. The video frame loads the real YouTube embed; clicking play starts it. Confirm the central play-button overlay toggles to "playing" (slightly transparent) state.
4. Confirm the scrubber tracks playback and that ticks appear at every question's timestamp.
5. Click ahead on the scrubber to a question's mark, let it play through; confirm the panel surfaces and playback pauses. Answer the question; confirm explanation appears and `Seguir` resumes playback.
6. Confirm the session panel updates from `1/N` to `2/N`, the answered question's circle goes green/red appropriately, and the new progress is reflected on Inicio (back-navigate, look at the card's progress bar).
7. Stop the backend mid-load → error state with Reintentar. Restart, click Reintentar, confirm recovery.
8. Navigate to `/listen/<bogus-id>` → 404 message + "Volver a Inicio" link works.
9. `pnpm lint`, `pnpm typecheck`, `pnpm build` all green.

### Confidence

**Level:** Medium

**Rationale:**

The two big unknowns are both in §How:

- **YouTube IFrame API integration with React + StrictMode + the existing TanStack Start SSR setup.** SSR is a real concern — the iframe API can only run client-side, so the `useYouTubePlayer` hook needs to be SSR-safe (no DOM access at module evaluation time, all script loading deferred to `useEffect`). The hook is straightforward in principle, but mistakes here surface as silent SSR/hydration mismatches, which have historically been painful to debug.
- **MCQ-due transition logic.** Triggering on every render where `currentTime ≥ question.timestamp` is the obvious pattern but creates a "fires forever" bug if not gated on "answered or already-pending." Same trap the design's prototype dodges. Pattern is well-known, but easy to get wrong.

Everything else is execution: queries already exist, styles are a port, panel structure is a 1:1 of the design.

**Validate before proceeding:**

1. **Spike — YouTube IFrame API hook.** ~30 min: write the hook in isolation, verify play / pause / seek / setPlaybackRate / onStateChange all work in dev, confirm SSR doesn't blow up (page renders without the iframe, hook attaches client-side, no hydration warnings).
2. **Spike — MCQ-due logic.** ~10 min: write the effect in isolation against a mock `currentTime` ticker, confirm a question fires exactly once even if the user seeks back past its timestamp and forward again (already-answered → don't re-fire; not answered but already pending → don't re-trigger).

If either spike comes back ugly, drop confidence to Low and re-spec.

### Key Decisions

- **YouTube IFrame API over a hosted-audio player.** We don't host the audio; YouTube does. The iframe API gives us the controls we need without bandwidth or storage cost. The trade-off — we depend on YouTube's iframe staying alive and staying API-compatible — is the same trade-off the rest of the product already makes (the data pipeline depends on yt-dlp / YouTube transcript API).
- **Trigger MCQs on `question.timestamp` directly, not via segment lookup.** Simpler. If the question's timestamp falls inside a segment, the pause feels natural; if it falls between segments, it feels equally natural. The segment-bound dance from the design prototype is mock-data-shaped, not real-data-shaped.
- **No tappable transcript yet.** Token-level data isn't in the backend. Plain segment text is good enough for the listening loop today. When 018 lands the token-level transcript and 016 lands Phrase Autopsy, we add tappable words and wire them into the autopsy panel.
- **Static `Narrador/a` speaker label.** Whisper segments don't carry speaker info. Adding diarisation is a separate backend concern. The label slot stays so when speaker info lands the swap is one line.
- **`useMutation` invalidates only the specific video's progress key.** Inicio's `useQueries` block keys on `['video-progress', v.video_id]` per video — the narrow invalidation hits exactly that one entry. Cheap and correct.
- **No transcript auto-scroll.** First-cut omission per non-goals. Re-introduces if manual smoke shows the active segment regularly leaves the viewport.

### Testing Approach

Same as 013/014: manual smoke is the bar. Frontend automated test infra is its own future spec. After implementation:

- `pnpm lint` clean
- `pnpm typecheck` clean
- `pnpm build` clean (client + SSR bundles)
- The nine manual-verification steps from §5 above
- Decision record at `015-escuchando/decision.md` recording: actual hook implementation pattern (any SSR pitfalls hit), the MCQ-due gating approach taken, any deviations from the design's CSS, behaviour of `setPlaybackRate` if applied before `onReady`.
