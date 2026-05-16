# Spec: Chunk library schema + endpoints

| Field | Value |
|---|---|
| id | 019 |
| status | approved |
| created | 2026-05-13 |

---

## Why

Mis frases — the saved-phrase library — is one of the three editorial pillars of the product (alongside MCQs and Phrase Autopsy). The design bundle (`docs/artefacts/project/data.js:198`) defines it: phrases Ana has saved, each annotated with where it came from and short speaking prompts that ask her to *use* the phrase, not just recognise it. Without 019 there is no persistence layer for any of that — every "save" toggle in the UI is session-local and forgotten on refresh.

019 ships the smallest persistent surface that lets Mis frases (020) render against real data: a `chunks` table, a `POST` that takes a phrase + the video it came from and writes a row with Claude-generated practice prompts, a global `GET` for the library screen, and a `DELETE` for unsave. That's it. No mastery, no recordings, no autopsy join — those are later features.

### Consumer Impact

- **Direct consumer: the planned Mis frases frontend (020).** 020 needs a real source of saved phrases to render its list, its prompt-rotation card, and (eventually) its "jump to source" affordance. Without 019, 020 is blocked on a fixture.
- **Indirect consumer: Ana, the single B2 learner.** Today's save toggle in `AutopsyPanel` (016) is session-local — close the tab, lose the phrase. 019 makes saves durable. Tap "guardar" on an autopsy → the phrase lands in Mis frases with its source and a handful of speaking prompts she can rotate through later.
- **016's save toggle becomes real.** Right now (`webapp/src/components/AutopsyPanel.tsx`) the save button is decorative. 020 wires it to `POST /api/chunks`; 016's UI doesn't move, only its handler.

### Roadmap Fit

- **Depends on:** nothing in the backend. The Claude integration pattern is already established by 017 (`services/phrase_autopsy.py`) and 018 (`services/phrase_markers.py`), and 017's `normalize_phrase` helper is reused for the cache key.
- **Soft-couples to:** 017 (`phrase_autopsy`). 019 deliberately does **not** FK to autopsy rows — chunks are standalone — but Mis frases may later resolve `(video_id, phrase_key)` against the autopsy cache to enrich the row at read time. That's a 020 decision, not a 019 schema choice.
- **Unblocks:** 020 (Mis frases frontend) and 021 (speaking-prompt audio recording — recordings attach to chunk + prompt pairs).
- **Doesn't block:** any frontend work already shipped. 016's save toggle stays session-local until 020 wires it.

---

## What

### Acceptance Criteria

- [ ] **`POST /api/chunks`** accepts `{ video_id: string, phrase: string, start_time: number }` where `video_id` is the YouTube id. Returns a `ChunkResponse` with `{ id, video_id (YouTube), source_title, phrase, start_time, prompts: [string], created_at }`.
- [ ] **Cache-hit semantics on save.** If a chunk already exists for `(video.id, phrase_key)`, the endpoint returns the existing row unchanged — no second Claude call, no duplicate row. Same response shape as a fresh save.
- [ ] **Cache miss generates prompts via Claude** using a Spanish-only prompt, parses the JSON response (a list of 2-4 strings), persists the row, and returns it. Round-trip on cache miss is bounded by Claude latency.
- [ ] **`GET /api/chunks`** returns all chunks across all videos, ordered newest-first (`created_at DESC`). Each row includes its `source_title` (the video title) so Mis frases can render it without a second fetch. May be empty.
- [ ] **`DELETE /api/chunks/{id}`** removes the row. 404 if it doesn't exist. Idempotent in the sense that a follow-up `DELETE` returns 404 cleanly.
- [ ] **Phrase normalization for the cache key.** Reuses `normalize_phrase` from 017 (`repositories/autopsy_repository.py`): trim → collapse internal whitespace → casefold. Stored `phrase` keeps original casing for display; `phrase_key` is the normalized lookup key.
- [ ] **Data shape is Spanish-only.** No `gloss` (the design's English field). Permanent per OVERVIEW §Non-Goals.
- [ ] **Validation.** 422 if `phrase` is empty / >200 chars, or `start_time` is negative. 404 if the YouTube `video_id` doesn't resolve to a `Video` row.
- [ ] **Claude failure handling.** If Claude returns malformed JSON or the call errors, the endpoint returns 502 with a Spanish error message; nothing is persisted. Same pattern as 017.
- [ ] **Alembic migration** creates the `chunks` table with appropriate indexes and a unique constraint on `(video_id, phrase_key)`.
- [ ] **Tests in the existing pytest suite** cover: save → row exists + prompts populated; save same phrase twice → second call is a cache hit (no Claude call, no duplicate); save with two casings → one row; list returns newest-first across videos; delete removes; delete-missing returns 404; malformed Claude response → 502, no row; video-not-found → 404; validation 422s.
- [ ] **Spike artefact.** Before locking the prompt, ~5-10 real phrases (drawn from a seeded video) are sent through a draft prompt; the generated speaking prompts are inspected for B2-appropriateness, variety (no three near-identical prompts), and the prompts actually *invite use of the phrase* (not just questions about it). Capture in the decision record.
- [ ] `ruff check` and `ruff format` clean.

### Non-Goals

- **Mastery / progress scoring.** Deferred. Comes back when 021 (recordings) lands and there's an actual signal to score from. No column in 019.
- **FK to `phrase_autopsy`.** Chunks are standalone. Mis frases can resolve autopsy data by `(video_id, phrase_key)` at read time if it ever wants to; the schema does not enforce a join.
- **Per-video chunk listing (`GET /api/videos/{id}/chunks`).** Mis frases is global; nothing on Escuchando asks "what have I saved on this video?" yet. If 020 surfaces this view, add the endpoint then.
- **Edit / PATCH on chunks.** Cache is write-once like 017. If a chunk's prompts are bad, delete and re-save.
- **Prompt regeneration on demand.** Same reason — write-once. A regen endpoint would invite the user to thrash the cache for free.
- **Spaced repetition / SRS algorithm.** No queue, no due-dates, no review intervals. Mis frases shows the rotation per the design; 019 just persists what was saved.
- **Speaking-prompt audio recordings.** That's 021. 019 stores the *prompts*, not their answers.
- **Multi-user / per-user scope.** Single-user product (OVERVIEW §Non-Goals); the cache is global.
- **Cross-video deduplication.** Same phrase saved on two different videos = two rows. Matches 017's per-video autopsy cache, and matches the design's `source` field semantics.
- **English `gloss` field.** Permanent product position (OVERVIEW §Non-Goals).

### Open Questions

1. **How much surrounding-segment context does the prompt generator need?** 017 found 1-2 segments around `start_time` was enough for autopsy. Speaking prompts may want less — the prompts are about *using* the phrase elsewhere, not parsing it in situ. Recommendation: start with the same `SegmentsRepository.context_around` window (1 segment) and let the spike show whether to widen.
2. **Phrase length cap: 200 vs ~80.** Spec inherits 200 from 017 for cache-helper consistency, but the *intent* is different: 017 caps "long enough to need grammar analysis," 019 caps "short enough to practice with prompts." The design's chunks are 2-20 chars; 200 chars is a 30-word sentence. In practice the API won't see paragraph-length chunks because saves originate from autopsy taps, which originate from short phrase-marker spans (018) — so 200 is a backstop, not a UX cap. Tightening to ~80 would still pass every design fixture and catch a future hand-rolled API caller pasting a paragraph. Decide post-spike, after seeing real chunk lengths.
3. **Normalization aggressiveness — special-char-only differences create duplicate cache rows.** The 017 `normalize_phrase` (whitespace + casefold only) leaves these as *distinct* keys: `«no me da igual»` vs `«no me da igual.»` (trailing period), `«¿sabes?»` vs `«sabes»` (leading/trailing punctuation), `«fíjate»` vs `«fijate»` (accent variant), `«no me da igual»` vs `no me da igual` (typographic quotes vs none). 017's defense was *"Ana taps a literal range — what she taps IS what she gets back"* — true today because every save originates from a canonical phrase-marker span. **But the schema doesn't enforce canonical origin.** If a future caller (search bar, free-text save) posts a hand-typed `phrase`, Mis frases shows duplicate-looking rows. Two ways to harden: (a) tighten the shared `normalize_phrase` to strip leading/trailing punctuation + typographic quotes (affects 017 too — low risk because existing rows are span-derived); (b) leave it alone and document the canonical-origin assumption until a feature breaks it. **Do not strip accents** — `más`/`mas`, `el`/`él`, `sí`/`si` are distinct words in Spanish and folding them merges legitimate pairs.
4. **Number of prompts per chunk.** Design shows 2-3; 017's autopsy uses 2-4 `natural_notes`. Prompt says "2 to 4." Adjustable in the prompt without a schema change.
5. **Ordering on `GET /api/chunks`.** `created_at DESC` matches "newest save first." If 020 wants a different default (e.g. by source video, by phrase alphabetical), we add a `?order=` param then.

---

## How

### Approach

#### Files added

```
src/api/routes/chunks.py                    # new router, /api/chunks
src/services/chunk_prompts.py               # ChunkPromptsService — Claude prompt + JSON parse
src/repositories/chunk_repository.py        # ChunkRepository — CRUD + (video_id, phrase_key) lookup
alembic/versions/{rev}_add_chunks.py        # migration
tests/test_chunk_prompts_service.py         # service-level: prompt construction, JSON parse, errors
tests/test_chunks_routes.py                 # endpoint-level: save / list / delete + edge cases
```

Files touched:

- `src/models/database.py` — add `Chunk` SQLModel + `chunks` back-reference on `Video`.
- `src/models/schemas.py` — add `ChunkSaveRequest`, `ChunkResponse`.
- `src/main.py` — register the new router.

#### Database model

```python
# src/models/database.py
class Chunk(SQLModel, table=True):
    __tablename__ = "chunks"
    __table_args__ = (UniqueConstraint("video_id", "phrase_key", name="uq_chunks_video_phrase"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    video_id: int = Field(foreign_key="videos.id", index=True)
    phrase: str                            # original casing for display
    phrase_key: str = Field(index=True)    # normalized for cache lookup
    start_time: float
    prompts: str                           # JSON string of [string]
    created_at: datetime = Field(default_factory=datetime.utcnow)

    video: Optional[Video] = Relationship(back_populates="chunks")
```

`chunks: List["Chunk"] = Relationship(back_populates="video")` added to `Video`.

#### Pydantic schemas

```python
# src/models/schemas.py
class ChunkSaveRequest(BaseModel):
    video_id: str                          # YouTube id
    phrase: str = Field(min_length=1, max_length=200)
    start_time: float = Field(ge=0)

class ChunkResponse(BaseModel):
    id: int
    video_id: str                          # YouTube id (for symmetry with the rest of the API)
    source_title: str                      # video title for Mis frases rendering
    phrase: str
    start_time: float
    prompts: list[str]
    created_at: datetime
```

#### Service

`src/services/chunk_prompts.py` follows the singleton pattern used by `services/questions.py` and `services/phrase_autopsy.py`:

```python
class ChunkPromptsService:
    def __init__(self) -> None:
        self._client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    def generate(self, phrase: str, context_segments: list[str]) -> list[str]:
        """Returns 2-4 Spanish speaking prompts that invite use of `phrase`.

        Raises ChunkPromptsGenerationError on parse failure or Claude error.
        """
```

The prompt is Spanish-only and asks Claude to:

1. Produce 2-4 Spanish speaking prompts in the imperative or interrogative form.
2. Each prompt should invite Ana to *use* the phrase in a fresh context (not analyse it, not translate it).
3. Vary register and scenario — at least one social/conversational, at least one personal/reflective.
4. Return strict JSON: a single array of strings. No prose outside the JSON.

Model: same one used by `phrase_autopsy.py` (`claude-4-sonnet-20250514`) for now — refresh is roadmap item 026, out of scope here.

The service does not know about caching, the database, or YouTube ids. It takes a phrase + context and returns a list. The route layer handles cache lookup and persistence.

#### Repository

```python
# src/repositories/chunk_repository.py
class ChunkRepository:
    def __init__(self, session: Session): ...

    def get_by_phrase(self, video_id: int, phrase_key: str) -> Chunk | None: ...
    def list_all(self) -> list[Chunk]: ...                       # newest-first
    def create(self, video_id: int, phrase: str, start_time: float, prompts: list[str]) -> Chunk: ...
    def delete(self, chunk_id: int) -> bool: ...                 # True if deleted, False if not found
    def to_response(self, row: Chunk, youtube_id: str, source_title: str) -> ChunkResponse: ...
```

`list_all` returns rows ordered `created_at DESC` with `video` eager-loaded so the route layer can read `youtube_id` and `title` without N+1.

`normalize_phrase` is imported from `repositories.autopsy_repository` — same helper for both caches, so the keys can never disagree.

#### Routes

```python
# src/api/routes/chunks.py
router = APIRouter(prefix="/api/chunks", tags=["chunks"])


@router.post("", response_model=ChunkResponse, status_code=201)
def save_chunk(body: ChunkSaveRequest, session: Session = Depends(get_session)):
    video = VideoRepository(session).get_by_youtube_id(body.video_id)
    if not video:
        raise HTTPException(404, "Video no encontrado")

    repo = ChunkRepository(session)
    key = normalize_phrase(body.phrase)
    cached = repo.get_by_phrase(video.id, key)
    if cached:
        return repo.to_response(cached, video.youtube_id, video.title)

    context = SegmentsRepository(session).context_around(video.id, body.start_time, window_seconds=6.0)
    try:
        prompts = chunk_prompts_service.generate(body.phrase, context)
    except ChunkPromptsGenerationError as exc:
        raise HTTPException(502, f"Generación de prompts fallida: {exc}") from exc

    row = repo.create(video.id, body.phrase, body.start_time, prompts)
    return repo.to_response(row, video.youtube_id, video.title)


@router.get("", response_model=list[ChunkResponse])
def list_chunks(session: Session = Depends(get_session)):
    rows = ChunkRepository(session).list_all()
    return [
        ChunkRepository(session).to_response(r, r.video.youtube_id, r.video.title)
        for r in rows
    ]


@router.delete("/{chunk_id}", status_code=204)
def delete_chunk(chunk_id: int, session: Session = Depends(get_session)):
    if not ChunkRepository(session).delete(chunk_id):
        raise HTTPException(404, "Chunk no encontrado")
    return Response(status_code=204)
```

Router registered in `src/main.py` next to the existing videos router.

#### Migration

Single Alembic revision adding `chunks` with the columns above, foreign key on `video_id`, index on `video_id`, index on `phrase_key`, unique constraint on `(video_id, phrase_key)`. Generated via `uv run alembic revision --autogenerate -m "add chunks table"`, manually checked.

#### Spike

Before merging this spec or writing the production prompt:

1. Draft the prompt locally in a one-off script.
2. Pick 5-10 phrases from a seeded video — mix idiomatic (`«no me da igual»`), filler/discourse (`«fíjate»`), grammatical (`«a eso de las nueve»`), and at least one phrase that depends on prior context.
3. Run each through the prompt. Inspect:
   - JSON parses cleanly.
   - 2-4 prompts each, no two prompts near-duplicates of each other within a chunk.
   - Each prompt invites *use* of the phrase, not analysis or translation.
   - Prompts are B2-readable, Spanish-only, no English crutches.
   - Output is stable across two runs (rough heuristic — exact match not required).
4. Capture the prompt, sample inputs, and one good + one weak output in `019-chunk-library/decision.md` once the feature lands.

If the spike fails (prompts come out generic, repetitive, or analytic instead of invitational), revisit the prompt. The schema is robust to prompt iteration — only the prompt text changes.

### Confidence

**Level:** Medium (Low until the spike passes).

**Rationale:**

The plumbing — endpoint + service + repository + Alembic migration + tests — is well-understood. 017 (`phrase_autopsy`) is a near-exact analog: same Claude singleton pattern, same `normalize_phrase` cache key, same on-demand-write-once cache, same 502-on-malformed-JSON pattern. The risk lives entirely in one question: *can Claude reliably produce 2-4 varied, invitational, B2-appropriate Spanish prompts for a given phrase?* The 017 spike resolved the analogous question for autopsy in ~30 minutes; this one is shaped the same way.

Once the spike confirms the prompt produces usable output, confidence rises to Medium. Not High even then because prompt quality for *speaking* prompts is editorially softer than for *grammar* explanations — there are more ways to be subtly bad (too analytic, too obvious, too repetitive). Prompt iteration is expected post-launch.

**Validate before proceeding:**

- Run the spike (5-10 phrases through a draft prompt; inspect output).
- Confirm `context_around(..., window_seconds=6.0)` produces enough surrounding context to ground the prompts. If prompts come out generic, widen the window or feed the full segment text.
- Confirm 200-char phrase cap is reasonable against real candidate phrases from seeded videos.

### Key Decisions

- **Standalone chunks — no FK to `phrase_autopsy`.** Decided in discovery. A chunk can be saved for a phrase that has no autopsy row (the design's mental model is "save = bookmark," not "save = bookmark + explanation"). If Mis frases later wants to enrich rows with autopsy data, it can resolve `(video_id, phrase_key)` against the autopsy cache at read time — no schema change required.
- **Claude-generated prompts at save time, persisted.** Decided in discovery. Alternative was on-demand-no-cache — rejected because every render of Mis frases would re-roll the prompts, breaking Ana's mental model of "these are *my* prompts." Cache is write-once: bad prompts get deleted and re-saved.
- **No `mastery` column in 019.** Decided in discovery. Mastery without recordings (021) is either decorative or self-rated; neither is worth carrying in the schema before the signal exists.
- **`/api/chunks` as a top-level router, not nested under `/api/videos`.** Mis frases is a global screen — its primary read is cross-video. Nesting under `/api/videos/{id}` would force a separate "list all my chunks" endpoint anyway. The save endpoint takes `video_id` in the body for symmetry.
- **Cache key is `(video_id, phrase_key)`, not `(phrase_key)` alone.** Same phrase saved on two different videos = two rows. Matches 017's autopsy semantics and the design's `source` field.
- **Phrase normalization reuses 017's helper.** `normalize_phrase` is whitespace + casefold only — no accent or punctuation stripping. Matches a literal-tap mental model.
- **Service does not know about caching.** Clean test boundary — service tests mock Claude only; route tests cover cache logic with the service mocked.

### Testing Approach

Follows the test infra established in 025 (pytest + DB fixture + monkeypatched service singletons).

**Service-level tests** (`tests/test_chunk_prompts_service.py`):

- Claude returns valid JSON array of 3 strings → service returns the list.
- Claude returns malformed JSON → `ChunkPromptsGenerationError`.
- Claude returns a JSON object instead of an array → `ChunkPromptsGenerationError`.
- Claude returns an array with non-string elements → `ChunkPromptsGenerationError`.
- Claude returns an empty array → `ChunkPromptsGenerationError` (require ≥2).
- Prompt construction includes the phrase and context segments verbatim.

**Route-level tests** (`tests/test_chunks_routes.py`):

- `POST /api/chunks` cache miss → calls service → persists → returns 201 with prompts populated and `source_title` set to the video title.
- `POST /api/chunks` cache hit → does NOT call service → returns the cached row with the same response shape.
- `POST /api/chunks` two casings of the same phrase on the same video → second call is a cache hit, only one row in the DB.
- `POST /api/chunks` same phrase on two different videos → two rows, both returned by `GET /api/chunks`.
- `POST /api/chunks` empty phrase → 422.
- `POST /api/chunks` phrase >200 chars → 422.
- `POST /api/chunks` negative `start_time` → 422.
- `POST /api/chunks` unknown YouTube id → 404.
- `POST /api/chunks` service raises `ChunkPromptsGenerationError` → 502, no row persisted.
- `GET /api/chunks` empty DB → `[]`.
- `GET /api/chunks` with 3 chunks across 2 videos → 3 entries, newest-first, each with the correct `source_title`.
- `DELETE /api/chunks/{id}` removes the row → 204; subsequent `GET` does not include it.
- `DELETE /api/chunks/{id}` for missing id → 404.

**Migration smoke** (covered implicitly by `tests/conftest.py` running migrations on the SQLite test DB): the new revision applies and the unique constraint blocks duplicates.

**No frontend tests.** Same deferral as 013–018. Frontend wiring lands with 020.

**Out of test scope:** real Claude calls. The spike captures the qualitative bar in the decision record; CI tests use mocks.
