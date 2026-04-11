# ComprendeYa Refactor Spec

Single-user app. Sequenced phases — each phase ships independently with its own acceptance criteria. Phase N assumes Phase N-1 is merged.

---

## Phase 1 — Monorepo conversion (mechanical, no behavior change)

**Goal:** restructure the repo so the FastAPI service and a new Next.js webapp live side by side, with zero functional change to the API.

### Layout

```
comprende-ya/
├── apps/
│   ├── api/                    # everything currently at repo root
│   │   ├── src/
│   │   ├── alembic/
│   │   ├── alembic.ini
│   │   ├── pyproject.toml
│   │   ├── uv.lock
│   │   ├── Dockerfile
│   │   ├── .dockerignore
│   │   └── .env
│   └── web/                    # new Next.js app (App Router, TypeScript)
│       ├── app/
│       ├── package.json
│       ├── next.config.ts
│       ├── tsconfig.json
│       └── .env.local
├── CLAUDE.md                   # updated with monorepo paths
└── README.md
```

### Tasks
1. `git mv` all current top-level project files into `apps/api/`. Verify `alembic.ini`'s `script_location` still resolves (relative path stays valid since both moved together).
2. Update `Dockerfile` build context references and any hardcoded paths.
3. Update `CLAUDE.md` commands to `cd apps/api && uv run …` form.
4. Scaffold `apps/web/` with `npx create-next-app@latest` — TypeScript, App Router, Tailwind, no `src/` dir, no ESLint config beyond default.
5. Add a root `.gitignore` covering `node_modules/`, `.next/`, `__pycache__/`.
6. Add `apps/web/.env.local.example` with `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`.

### Out of scope
- Workspace tooling (pnpm/Turbo/Nx).
- Shared type generation.
- Any API or schema change.

### Acceptance criteria
- `cd apps/api && uv sync && uv run fastapi run src/main.py` works as before.
- `cd apps/api && alembic upgrade head` works.
- `cd apps/web && npm run dev` serves the default Next.js page on `:3000`.
- Existing CORS rule (`localhost:3000`) still applies — no API code change needed.

---

## Phase 2 — Watch Mode UI

**Goal:** a usable Watch Mode in the Next.js app that drives the existing `/api/videos/process-async` pipeline end-to-end and renders questions at the right timestamps.

### Backend changes
Minimal — the existing endpoints already cover most of this. Add only:
1. `GET /api/videos/{video_id}` — fetch a processed video with its questions and segments (if not already exposed in the shape the frontend needs).
2. `POST /api/videos/{video_id}/questions/{question_id}/grade` — accepts `{ user_answer: string }`, calls Claude as an LLM judge, returns `{ correct: bool, feedback: string, ideal_answer: string }`. No persistence in this phase beyond logging.
3. `POST /api/tts` — proxies to Cartesia. Body `{ text: string, voice_id?: string }`, returns audio stream (`audio/mpeg` or whatever Cartesia returns). Add `CARTESIA_API_KEY` to `config.py` and `.env.example`. Stateless — no DB writes.
4. New service module `apps/api/src/services/tts.py` (Cartesia client) and `apps/api/src/services/grader.py` (LLM judge prompt + Claude call).

### Frontend
1. **Mode toggle** at top of app: `[Watch Mode] [Review Mode]` — Review Mode is a placeholder until Phase 4.
2. **URL submission view**: input + submit → `POST /api/videos/process-async`, then poll `GET /api/videos/status/{flow_run_id}` until done, then route to the watch view with the resulting `video_id`.
3. **Watch view layout** (matches the sketch):
   - Left ~60%: YouTube IFrame Player API embed. Track `currentTime` via the player API (poll at ~250ms or use `onStateChange` + `requestAnimationFrame`).
   - Right ~40%: Question Panel (idle state by default).
   - Bottom strip: "Session Phrases" — empty in this phase, populated in Phase 3.
4. **Question firing logic**:
   - On video load, fetch the video's questions (each has a `timestamp`).
   - Maintain a sorted queue of upcoming questions. When `currentTime` crosses the next timestamp, call `player.pauseVideo()` and activate the panel with that question.
   - Panel shows: question text, "🔊 Hear Question" button (calls `/api/tts`), text input, "Submit" and "Hear Answer" buttons.
   - Submit → `POST .../grade` → render feedback inline. After feedback, "Continue" resumes playback and advances the queue.
5. **TTS playback**: simple `<audio>` element with `src` set to a blob URL from the `/api/tts` response. No caching in this phase.

### Out of scope
- Phrase highlighting / phrase events (comes in Phase 3).
- Saving session state to DB.
- Persistence of grades.

### Acceptance criteria
- User pastes a YouTube URL, sees a loading state, then lands on the watch view.
- Video plays; at each question timestamp the video pauses and the question panel becomes active.
- Clicking the TTS button plays Cartesia audio of the question.
- Submitting an answer returns judged feedback within ~3s.
- "Continue" resumes the video and the next question fires correctly.

---

## Phase 3 — Phrase bank: model, extraction, save flow

**Goal:** during video processing, run a new Claude pass that extracts idioms/colloquialisms; expose them in the watch view as saveable items; persist a deduplicated phrase bank.

### Data model (new SQLModel tables)

```
Phrase
  id: UUID (pk)
  text: str (unique, normalized)         # "o sea"
  text_normalized: str (unique, indexed) # lowercase, accent-stripped, used for dedup
  meaning: str
  register: enum(colloquial, neutral, formal)
  region: str | None                     # "España", "México", "general"
  first_seen_at: datetime
  # FSRS fields added in Phase 4

PhraseOccurrence
  id: UUID (pk)
  phrase_id: FK -> Phrase
  video_id: FK -> Video
  timestamp_seconds: float
  context_snippet: str                   # ±1 sentence around the occurrence
  saved_to_bank: bool (default False)
  created_at: datetime
```

`Phrase` is the deduplicated bank entry. `PhraseOccurrence` records every time a phrase shows up in any video, even before the user saves it. "Saving to bank" flips `saved_to_bank=True` on the occurrence and ensures the parent `Phrase` row exists. Dedup key is `text_normalized`.

Alembic migration adds both tables.

### Extraction flow
1. New service `apps/api/src/services/phrase_extractor.py`. Single function that takes the full transcript text + segments and calls Claude with a structured prompt: "Extract idioms, colloquialisms, and phrasal expressions notable for an intermediate Spanish learner. For each: text, meaning in English, register, region (if regional), the timestamp from the nearest segment, and a short context snippet." Return a Pydantic model list.
2. Wire into `flows/video_processing.py` as a new task that runs after transcription, in parallel with the existing question generation. On completion, upsert `Phrase` rows (by `text_normalized`) and insert `PhraseOccurrence` rows.
3. New repository `phrase_repository.py` with: `upsert_phrase`, `create_occurrence`, `list_occurrences_for_video`, `mark_occurrence_saved`, `list_saved_phrases`.

### API endpoints
- `GET /api/videos/{video_id}/phrases` → list of `PhraseOccurrence` joined with `Phrase`, ordered by timestamp.
- `POST /api/phrases/occurrences/{occurrence_id}/save` → marks `saved_to_bank=True`.
- `DELETE /api/phrases/occurrences/{occurrence_id}/save` → unsave.
- `GET /api/phrases` → all phrases that have at least one saved occurrence (the user's bank).

### Frontend
1. Watch view fetches `/api/videos/{video_id}/phrases` alongside questions.
2. **Session Phrases strip** (bottom of watch view) renders one chip per occurrence. Chip shows phrase text + a save toggle. Tooltip on hover shows meaning + context.
3. As the video plays, chips for occurrences within the current ±5s window get a subtle highlight (visual cue only — no pause).
4. Optional: at end of video, show a "Session Summary" modal listing all occurrences with bulk-save checkboxes. (Stretch goal — can defer if it bloats the phase.)

### Comprehension-questions-about-phrases
The existing question generator already produces phrase-flavored questions. No change required here — the question pipeline and phrase extraction run independently. A future enhancement can cross-link a `Question` to a `Phrase` row, but it's out of scope for this phase.

### Out of scope
- SRS scheduling fields (Phase 4).
- Review mode (Phase 4).
- Editing phrase text/meaning by hand.

### Acceptance criteria
- Processing a new video populates `phrases` and `phrase_occurrences` tables.
- Re-processing a video that contains "o sea" when "o sea" already exists creates a new occurrence but reuses the same `Phrase` row.
- Watch view bottom strip shows the extracted phrases for the current video.
- Clicking save on a chip persists; reloading the page reflects the saved state.
- `GET /api/phrases` returns only phrases the user has explicitly saved.

---

## Phase 4 — Review Mode + FSRS + on-demand example sentences

**Goal:** a working Review Mode that surfaces due phrases, generates a fresh example sentence each time, runs the user through a confidence-rated review, and updates FSRS state.

### Schema additions
Extend `Phrase` with FSRS fields (Alembic migration):

```
Phrase (additions)
  fsrs_difficulty: float | None
  fsrs_stability: float | None
  fsrs_retrievability: float | None
  fsrs_state: enum(new, learning, review, relearning) default 'new'
  fsrs_due_at: datetime | None          # when this card is next due
  fsrs_last_reviewed_at: datetime | None
  fsrs_reps: int default 0
  fsrs_lapses: int default 0
```

New table for review history and generated examples:

```
PhraseReview
  id: UUID (pk)
  phrase_id: FK -> Phrase
  rating: enum(again, hard, good, easy)   # FSRS 4-button scale
  reviewed_at: datetime
  example_sentence: str                   # the sentence that was shown
  user_response: str | None
  judge_feedback: str | None

PhraseExampleSentence
  id: UUID (pk)
  phrase_id: FK -> Phrase
  text: str
  generated_at: datetime
```

`PhraseExampleSentence` is the "history" — every generated sentence is stored so we can pass prior examples to Claude with an instruction to never repeat.

### FSRS integration
- Add the [`fsrs`](https://pypi.org/project/fsrs/) package to `pyproject.toml`.
- New service `apps/api/src/services/srs.py` wrapping the library: `schedule_new(phrase)`, `apply_review(phrase, rating) -> updated fsrs fields`. Default parameters; no per-user tuning in v1.
- When a `PhraseOccurrence` is first saved (Phase 3 endpoint), initialize the parent `Phrase`'s FSRS state to `new` with `fsrs_due_at = now()` if not already set.

### Example sentence generation
- New service `apps/api/src/services/example_generator.py`. Takes a `Phrase` and the list of prior `PhraseExampleSentence.text` values. Calls Claude with: "Generate one fresh Spanish example sentence using the phrase '{text}' (meaning: '{meaning}'). Do not reuse any of these prior sentences: [...]. Match the register: {register}." Returns the new sentence; caller persists it.
- On-demand only — no pre-generation batch.

### API endpoints
- `GET /api/review/due?limit=20` → next due phrases ordered by `fsrs_due_at`. Each item includes the phrase + a freshly generated example sentence (and persists the `PhraseExampleSentence` row).
- `POST /api/review/{phrase_id}/grade` → body `{ user_response: string, example_sentence_id: UUID }`. LLM-judge scores the response (reuses Phase 2 grader, with a phrase-aware prompt). Returns `{ correct, feedback }` and a recommended FSRS rating heuristic — but the user picks the actual rating.
- `POST /api/review/{phrase_id}/rate` → body `{ rating: again|hard|good|easy, example_sentence_id, user_response?, judge_feedback? }`. Applies FSRS update, writes `PhraseReview`, returns updated `fsrs_due_at`.

The split between `/grade` and `/rate` lets the user hear feedback before committing a rating, matching the flow in your overview.

### Frontend
1. **Mode toggle** routes to `/review`.
2. **Review session view**:
   - Top: count of remaining due cards.
   - Card: phrase text is *hidden* initially; only the example sentence is shown (and a 🔊 button to TTS the sentence via Phase 2's `/api/tts`).
   - User types what they think the phrase is / what it means / a response using it.
   - Submit → `POST /grade` → reveal the phrase, meaning, and feedback.
   - Four rating buttons (Again / Hard / Good / Easy) → `POST /rate` → next card.
3. **Empty state**: "No phrases due. Come back later or watch a new video."

### TTS reuse
The `/api/tts` endpoint from Phase 2 is used unchanged — it's stateless and serves both modes.

### Out of scope
- Per-user FSRS parameter tuning.
- Review heatmaps / stats dashboards.
- Bulk import/export of the phrase bank.
- Audio caching.

### Acceptance criteria
- Saving a phrase in Watch Mode immediately makes it eligible for review (`fsrs_due_at` set).
- `GET /api/review/due` returns phrases in due order; each call to a given phrase produces a new example sentence not present in `phrase_example_sentences`.
- Submitting a review updates `fsrs_due_at` according to the FSRS library's calculation and inserts a `PhraseReview` row.
- After rating "Again", the phrase reappears in the due list within the same session; after "Easy", it pushes out by days.
- TTS plays the example sentence on demand.

---

## Defaults chosen on your behalf
- **YouTube player**: official IFrame API (not a wrapper library) — fewer dependencies, full control over `currentTime` polling.
- **Polling vs websockets** for processing status: keep the existing polling endpoint; no websocket layer.
- **Phrase normalization**: lowercase + Unicode NFD accent strip, applied server-side before dedup lookup.
- **Cartesia voice**: a single hardcoded Spanish voice ID in config; not user-selectable in v1.
- **No tests added** — the project has none today; this spec doesn't introduce a test suite. Flag if you'd like me to bake one in.

Anything to adjust before I start Phase 1?
