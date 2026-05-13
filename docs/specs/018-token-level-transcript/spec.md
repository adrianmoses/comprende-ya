# Spec: Token-level transcript with phrase-span markers

| Field | Value |
|---|---|
| id | 018 |
| status | approved |
| created | 2026-05-09 |

---

## Why

Today the transcript Ana sees in the Escuchando view is plain text: she can read it, the current segment highlights as the audio plays, but she has no way to point at something she didn't parse. The Phrase Autopsy panel exists (016) and the autopsy generator exists (017), but the only thing wired up to *trigger* a panel open is a temporary "Frases destacadas" list in the right rail, marked `temporal · ver 018`, populated from a hand-written fixture (`webapp/src/data/autopsy-fixtures.ts`). 018 turns the transcript itself into the surface where Ana points: marked phrase spans render as visually tappable, tapping a span calls `POST /api/videos/{id}/autopsy/explain`, the panel opens against real Claude output. The fixture and the rail trigger go away with the same change.

This is the missing connector between 016 (UI exists), 017 (data path exists), and Ana's actual job ("when something sounds native but I can't parse it, let me point at it"). Without 018 the autopsy feature is permanently demo-shaped.

### Consumer Impact

- **Direct consumer: the Escuchando frontend (`webapp/src/routes/listen.$id.tsx`) and Ana, the single B2 learner.** The transcript renders the same plain text it does today, plus visually distinct phrase spans where Claude flagged something worth inspecting. Tapping inside a span opens the existing `AutopsyPanel` against the live endpoint. Tapping unmarked words does nothing — by design.
- **Indirect consumer: 017's cache.** The same Claude call that produces marker spans also produces the autopsy payload for each marked phrase, so we pre-populate `phrase_autopsy` rows during processing. First-tap latency drops to a DB lookup; the autopsy panel feels instant.
- **Retires**: 016's "Frases destacadas" temporary trigger and the `autopsy-fixtures.ts` fixture file. After 018 the panel is exclusively driven by tappable transcript spans.

### Roadmap Fit

- **Depends on:** 017 (autopsy endpoint + `phrase_autopsy` table + `normalize_phrase` helper). 018 writes into the same table 017 reads from on cache hit.
- **Soft-couples to:** 016 (`AutopsyPanel` is the renderer) and 015 (transcript layout in `listen.$id.tsx` is where tappable spans land).
- **Unblocks:** 020 (Mis frases / chunk library — saved phrases reference autopsy rows that 018 starts pre-populating).
- **Doesn't block:** further backend features. 022/024 are independent.

---

## What

### Acceptance Criteria

- [ ] **Token storage on `VideoSegment`.** A new nullable `tokens` JSON column carries the per-segment token list. Legacy segments (rows that existed before 018) read back as `tokens: null` until backfilled and the frontend treats null as "no markers, render plain text."
- [ ] **Token shape.** Each token is one of:
  - `{ "t": "<word>" }` — a word token outside any marker span.
  - `{ "t": "<word>", "span": <int>, "start": true }` — the first word of a marker span. `span` is a per-segment index (0, 1, 2, …).
  - `{ "t": "<word>", "span": <int> }` — a non-first word inside a marker span.
  - `{ "p": "<punct>" }` — punctuation. Never carries `span` (punctuation isn't tappable).
- [ ] **Marker generation in `process_video_flow`.** A new task between `save_video_segments` and `generate_exercises_task` calls Claude once with the full transcript (segments numbered, start times included) and gets back a list of `{ phrase, segment_number, tokens_in_segment, register, grammar, natural_notes }` entries. Bounded at 5–15 phrase markers per video.
- [ ] **Pre-warm 017's cache.** For every marker phrase Claude returns, the flow inserts a `phrase_autopsy` row using the same `normalize_phrase` helper 017's route uses. On `(video_id, phrase_key)` conflict the existing row wins (`ON CONFLICT DO NOTHING`) — manual taps that already populated the cache aren't overwritten.
- [ ] **Span localisation.** For each marker, the flow tokenises the named segment via spaCy and finds the contiguous run of word tokens matching `tokens_in_segment`. If no contiguous match exists, the marker is skipped (logged, not fatal). All other tokens in the segment still get their `tokens` list populated.
- [ ] **Punctuation preserved.** The token list reproduces every word and punctuation mark in the original `transcript_text` in order. Joining `t`/`p` values with appropriate spacing reconstructs (close to) the segment text.
- [ ] **`GET /api/videos/{video_id}/segments` extended.** The existing endpoint's response gains a `tokens` field per segment (the JSON column, deserialised). No new endpoint. Schema is additive — existing callers ignore it.
- [ ] **Frontend wiring.** `listen.$id.tsx` renders tappable phrase spans (one click target per span, regardless of which token in the span was clicked). Tap fires `POST /api/videos/{id}/autopsy/explain` with `{ phrase: <span text>, start_time: <segment.start_time> }`; success opens `AutopsyPanel` with the response; the existing "Frases destacadas" trigger and the import of `autopsy-fixtures.ts` are removed.
- [ ] **Loading + error states.** Tap → request inflight → panel shows a Spanish loading state ("Generando autopsia…"). 502 error → panel shows "No se pudo generar la autopsia." with a Reintentar button. Cache hit on the backend means tap-to-render is essentially instant; loading state appears only when the cache is somehow cold (e.g., legacy video, manual cache eviction).
- [ ] **Validation.** 422 if Claude returns ≥1 marker entry that fails the autopsy schema (the same `_validate_payload` 017 already uses). Generation failure (Claude error, JSON parse error, all markers invalid) does **not** fail the whole flow — segments + exercises still ship; only `tokens` stays null and the cache stays unpopulated. Logged for editorial review.
- [ ] **Spike artefact.** Before locking the prompt, run a spike on 1–2 seeded videos (`m1DFpkNdcv0` plus one new processed video). Inspect: marker phrases are editorially good for B2; `tokens_in_segment` actually appears contiguously in the named segment ≥80% of the time; autopsy payloads pass 017's validator; no English crutches. Spec moves from `draft` to `approved` only after the spike passes.
- [ ] **Tests.** New tests in `tests/`: marker service (mocked Claude); flow step (marker generation + persistence + cache pre-warm + spaCy tokenisation); extended `/segments` response shape; conflict path (pre-existing autopsy row wins).
- [ ] `ruff check`, `ruff format`, `pnpm typecheck`, `pnpm lint` clean.

### Non-Goals

- **Tapping unmarked words.** Free-form vocabulary lookup ("what does *X* mean") is a different feature with a different quality bar (B2 dictionaries, not autopsy generators) and isn't on the roadmap. Only marked spans are click targets.
- **Spans that cross segment boundaries.** Marker phrases must live inside a single `VideoSegment`. If a phrase straddles a Whisper segment break in the wild, it's skipped. Whisper segments at sentence/pause boundaries; idioms tend to stay together. We revisit if that turns out to bite.
- **Word-level Whisper timestamps.** Today Whisper is called with `timestamp_granularities=["segment"]`. Span replay uses the *segment*'s `start_time`, not a word-level offset. Upgrading Whisper's call costs payload size and isn't required for the panel's "Re-escuchar" button.
- **Cross-video phrase reuse.** Each video's markers are independent; a phrase appearing in two videos gets two separate `phrase_autopsy` rows (same shape as 017's cache).
- **Backfill of existing videos.** Legacy `VideoSegment` rows stay with `tokens: null`. A one-shot script can backfill them later if it matters; spec doesn't require it.
- **In-place marker editing / regeneration endpoints.** No `PATCH /tokens`, no "regenerate markers." Same write-once stance as 017.
- **Marker quality / confidence scores.** No per-phrase confidence on the row.
- **Claude as the tokeniser.** spaCy owns tokenisation (already loaded for 007). Claude only names *which phrases* are interesting; the flow does the actual segment → token list work.

### Open Questions

1. **What's the right marker density?** Spec caps at 5–15 per video, biased toward "fewer, more editorial" over "many, more generous." The spike will tell us if 5 is too few for a 30-minute video or 15 is too many for a 5-minute clip. Adjustable post-spike based on real density.
2. **Visual treatment of marker spans.** The frontend wiring section assumes a single style (e.g., subtle underline + hover). Final visual is a small editorial choice; doesn't affect the data shape. Defer to implementation.
3. **What happens if Claude returns an "interesting" phrase that's a single word?** Span data shape allows length-1 spans — they still render as a tappable region. Whether to *encourage* multi-word phrases in the prompt is an editorial knob in the spike.

---

## How

### Approach

#### Files added

```
src/services/phrase_markers.py             # PhraseMarkersService — Claude prompt + parse
src/services/segment_tokenizer.py          # spaCy-driven tokeniser; shared, side-effect-free
alembic/versions/{rev}_add_segment_tokens.py
tests/test_phrase_markers_service.py
tests/test_segment_tokenizer.py
tests/test_video_processing_markers.py     # flow-step integration test
```

Files touched:

- `src/models/database.py` — add nullable `tokens: Optional[str]` JSON column to `VideoSegment`.
- `src/flows/video_processing.py` — add `generate_phrase_markers_task` + `save_phrase_markers_task` between `save_video_segments` and `generate_exercises_task`.
- `src/api/routes/videos.py` — `GET /{video_id}/segments` deserialises and includes `tokens`.
- `webapp/src/routes/listen.$id.tsx` — render tappable spans, swap fixture trigger for live API.
- `webapp/src/components/AutopsyPanel.tsx` — accept loading/error states alongside the existing `entry` prop.
- `webapp/src/components/AutopsyTriggerCard.tsx` — delete (subsumed by the transcript itself).
- `webapp/src/data/autopsy-fixtures.ts` — delete.

#### Database

```python
# src/models/database.py — additive change to VideoSegment
class VideoSegment(SQLModel, table=True):
    ...
    tokens: Optional[str] = None  # JSON string of the per-segment token list
```

The existing 017 `phrase_autopsy` table needs no schema change — 018 just inserts more rows into it during the flow.

#### Token shape (in the JSON column)

```json
[
  { "t": "Mira" },
  { "p": "," },
  { "t": "no", "span": 0, "start": true },
  { "t": "me", "span": 0 },
  { "t": "da", "span": 0 },
  { "t": "igual", "span": 0 },
  { "p": "." }
]
```

Span indices are local to a segment (0, 1, 2, …). The frontend reconstructs the phrase text by joining the `t` values of all tokens with the same `span` value (with single spaces between them, since spans are word runs).

#### `PhraseMarkersService`

`src/services/phrase_markers.py` follows the singleton pattern. One public method:

```python
class PhraseMarkersService:
    def explain_video(
        self,
        segments: list[VideoSegment],
    ) -> list[MarkerEntry]:
        """Returns a list of MarkerEntry, each carrying a phrase + segment_number
        + tokens_in_segment + a fully-formed AutopsyPayload (017's shape).

        Raises PhraseMarkersGenerationError on call/parse failure.
        """
```

`MarkerEntry` is a TypedDict in the service module:

```python
class MarkerEntry(TypedDict):
    phrase: str
    segment_number: int
    tokens_in_segment: list[str]
    register: str
    grammar: list[dict]
    natural_notes: list[str]
```

Prompt asks Claude (Spanish-only) to:
1. Read the full transcript with segment numbers.
2. Pick 5–15 phrase spans worth Ana tapping (idioms, register-marked phrases, grammatical pressure points).
3. For each, list the segment number it lives in and the exact word tokens (no punctuation) that make up the span.
4. For each, produce the autopsy payload using the *exact same JSON shape* `_validate_payload` in `services/phrase_autopsy.py` already validates.

The prompt mirrors 017's prompt for the autopsy portion verbatim (literal copy of the schema description + register/grammar/natural_notes rules) so the two stay aligned. 026 will sweep both files together.

Model: `claude-4-sonnet-20250514` (matches 017 and `services/questions.py`). Max tokens bumped to ~4000 since the response carries N×autopsy payloads.

Service is unaware of the database — it returns the parsed list and lets the flow decide what to persist.

#### `SegmentTokenizer`

`src/services/segment_tokenizer.py` exposes a pure function:

```python
def tokenize_segment(
    text: str,
    span_phrases: list[tuple[int, list[str]]],  # (span_index, token_list)
    nlp: spacy.Language,
) -> list[dict]:
```

Tokenises `text` via spaCy, classifies each token as word vs. punctuation, and walks `span_phrases` to assign `span` indices to the contiguous matching runs. If a phrase's token list doesn't appear contiguously in `text`, the span is dropped (caller logs, no exception).

The flow loads spaCy once (already does, for `frase_exercise_generator`); we reuse the same `nlp` object rather than loading a second one.

#### Flow integration

```python
# src/flows/video_processing.py — between save_video_segments and generate_exercises_task

@task
def generate_phrase_markers_task(video_id: int, segments: list[VideoSegment]) -> list[MarkerEntry]:
    return phrase_markers_service.explain_video(segments)

@task
def save_phrase_markers_task(video_id: int, segments: list[VideoSegment], markers: list[MarkerEntry], nlp: spacy.Language):
    # Group markers by segment_number so we tokenise each segment exactly once.
    by_segment: dict[int, list[MarkerEntry]] = defaultdict(list)
    for m in markers:
        by_segment[m["segment_number"]].append(m)

    with get_db_session() as db:
        autopsy_repo = AutopsyRepository(db)
        for seg in segments:
            seg_markers = by_segment.get(seg.segment_number, [])
            span_phrases = [(i, m["tokens_in_segment"]) for i, m in enumerate(seg_markers)]
            tokens = tokenize_segment(seg.transcript_text, span_phrases, nlp)
            seg.tokens = json.dumps(tokens, ensure_ascii=False)
            db.add(seg)

            for i, m in enumerate(seg_markers):
                # Insert the autopsy row; existing rows win (manual taps may have
                # populated the cache before processing finished).
                phrase_key = normalize_phrase(m["phrase"])
                if autopsy_repo.get_by_phrase(video_id, phrase_key):
                    continue
                autopsy_repo.create(
                    video_id=video_id,
                    phrase=m["phrase"],
                    start_time=seg.start_time,
                    payload=AutopsyPayload(
                        register=m["register"],
                        grammar=m["grammar"],
                        natural_notes=m["natural_notes"],
                    ),
                )
        db.commit()
```

Failure handling: if `generate_phrase_markers_task` raises, the flow logs the error and continues to `generate_exercises_task` with no markers. Segments end up with `tokens: null` and the cache stays unpopulated — the frontend gracefully falls back to plain text.

#### Endpoint

`GET /api/videos/{video_id}/segments` already returns the segment rows. Update its serialiser to include `tokens` (deserialised from JSON):

```python
return [
    {
        "id": s.id,
        "video_id": s.video_id,
        "segment_number": s.segment_number,
        "transcript_text": s.transcript_text,
        "start_time": s.start_time,
        "end_time": s.end_time,
        "tokens": json.loads(s.tokens) if s.tokens else None,
    }
    for s in segments
]
```

No new route. The webapp's `getVideoSegments()` API helper signature is unchanged; only the response type widens.

#### Migration

Single Alembic revision adding `tokens` (nullable JSON string) to `video_segments`. Generated via autogenerate, manually checked.

#### Frontend

`listen.$id.tsx`:

1. Strip the import + render of `AutopsyTriggerCard` and the `getAutopsyEntries(youtubeId)` lookup.
2. Strip `getAutopsyEntry` import.
3. Render the transcript by walking `segment.tokens` (when present): plain spans for `{t}` tokens with no `span`, tappable wrappers around runs of tokens sharing a `span` index, plain spans for `{p}` punctuation.
4. On tap, build the phrase text by joining `{t}` values inside the span, call `POST /api/videos/{youtubeId}/autopsy/explain` with `{ phrase, start_time: segment.start_time }`, store the response in component state, open the panel.
5. While inflight: panel shows loading state. On 502: panel shows error + retry. On success: panel renders against the `AutopsyEntry` returned.
6. Delete `webapp/src/data/autopsy-fixtures.ts` and `webapp/src/components/AutopsyTriggerCard.tsx`.

`AutopsyPanel.tsx` accepts an extended prop shape:

```ts
type AutopsyPanelProps =
  | { state: "loading"; phrase: string; onClose: () => void }
  | { state: "error"; phrase: string; onClose: () => void; onRetry: () => void }
  | { state: "loaded"; entry: AutopsyEntry; isSaved: boolean; onClose: () => void; onSave: () => void; onReplay: () => void };
```

CSS for tappable spans: a single rule for `.tx-span` (subtle underline / hover background, cursor pointer). Inactive tokens render as plain `<span>`. Final visual is an editorial choice during implementation — not pinning it in the spec.

#### Spike

Before locking the prompt:

1. Write a one-off script (not committed; matches 017's spike pattern) that calls the draft prompt against `claude-4-sonnet-20250514` for one or two real videos.
2. Validate per-entry: `tokens_in_segment` appears contiguously in the named segment ≥80% of the time; autopsy payloads pass `_validate_payload`; phrases are 1–6 words; no English; no duplicates.
3. Editorially review: are these the phrases Ana should tap? Subjective but answerable by reading 5 entries.
4. Capture one good and one borderline output verbatim in `decision.md` once the feature lands.

If the spike fails on payload shape or contiguity, adjust the prompt before writing service code. If quality is the issue, iterate the prompt and re-spike.

### Confidence

**Level:** Medium (after the spike; Low until then).

**Rationale:**

The plumbing is well-trodden — service singleton, repository pattern, Prefect task addition, Alembic migration, additive endpoint field, frontend wiring patterns we've used in 015/016. The risk lives in two coupled places:

1. **Editorial quality of Claude's marker choices.** Generating an autopsy for a phrase you've handed Claude (017) is a well-defined task; *deciding which phrases to mark* is a softer editorial call. The spike is the cheap way to check whether Claude's "interesting" matches Ana's "interesting."
2. **Span localisation reliability.** Claude has to name the exact word tokens in the named segment. Whitespace, accents, contractions, capitalisation can all trip a contiguous-match check. Mitigation is normalisation (casefold + accent-strip *only for matching*, not for storage) and graceful degradation (skip the span, log it, keep going). Spike measures the actual hit rate.

Once the spike confirms both, confidence is Medium. Not High because data quality is editorial — "is this actually useful to Ana" is a judgment we'll iterate on, but the storage shape and the API surface should be stable after the spike.

**Validate before proceeding:**

- Run the spike (1–2 videos × draft prompt; inspect contiguity rate, payload validity, editorial quality).
- Confirm 5–15 markers per video is the right ballpark on real videos.
- Confirm spaCy + Claude tokens line up reliably; if not, choose between (a) a fuzzier matching strategy or (b) asking Claude for character offsets instead of token lists.

### Key Decisions

- **JSON column on `VideoSegment` rather than a new `VideoToken` table.** Tokens are read every time the segment is read, never queried independently, never indexed. A column matches access shape; a table would add a join for no reason.
- **One Claude call per video, not per segment.** Whole-transcript context is exactly what marker selection needs — "is this phrase interesting?" is partly a function of "compared to what else is in this video." Per-segment calls would lose that context and cost N× more.
- **Combined marker + autopsy in one call.** Two birds. Couples 017's and 018's prompts but the schemas were already supposed to match; tying them at the prompt level enforces that.
- **`ON CONFLICT DO NOTHING` on autopsy pre-warm inserts.** A user who tapped a phrase before processing finished gets the autopsy *they* triggered; the flow's pre-warm only fills empty slots. Avoids overwriting context-aware autopsies with batch-generated ones.
- **Spans are intra-segment.** Cross-segment phrases are out of scope. Whisper splits at pauses; idioms rarely cross those breaks.
- **spaCy tokenises, Claude marks.** Don't ask Claude to do tokenisation it can drift on. Claude names phrases, spaCy turns the segment text into a token list, the flow reconciles the two.
- **`tokens` is nullable.** Legacy segments stay legacy. Frontend treats null as plain-text fallback.
- **No backfill.** Existing videos are pre-018; users can re-process if they want markers.
- **Marker generation failure ≠ flow failure.** Markers are editorial polish on top of the existing pipeline. If Claude is down, segments + exercises still ship; only the panel-trigger feature stays cold.
- **Frontend wiring lands with the backend in this branch.** Splitting them would mean shipping a backend that 016 still ignores, with the fixture still loaded — no observable user-facing change. Same-branch wiring matches how 014 and 015 shipped.

### Testing Approach

Follows the test infra established in 025.

**Service-level tests** (`tests/test_phrase_markers_service.py`):
- Claude returns valid markers → service returns parsed `list[MarkerEntry]`.
- Claude returns malformed JSON → `PhraseMarkersGenerationError`.
- One entry's autopsy payload is invalid → that entry is dropped, others returned.
- Prompt construction includes every segment with its number and start time.

**Tokenizer tests** (`tests/test_segment_tokenizer.py`):
- Plain text segment with no spans → all `{t}` / `{p}` tokens, no `span` keys.
- Single-span segment → first matching word gets `start: true`, span index 0.
- Two-span segment → indices 0 and 1, both with `start: true` on their first word.
- Phrase that doesn't appear contiguously → silently dropped from the output (no exception).
- Punctuation-heavy text → `{p}` tokens preserve their original characters.

**Flow-step tests** (`tests/test_video_processing_markers.py`):
- Mocked `phrase_markers_service.explain_video` → 1 marker → segment row's `tokens` is populated, `phrase_autopsy` row exists with `phrase_key` matching `normalize_phrase(phrase)`.
- Mocked service raises → flow continues, `tokens` stays null, no autopsy rows inserted, exercises still generate.
- Pre-existing autopsy row for the same `phrase_key` → flow skips the insert (existing row wins), no `IntegrityError`.

**Route-level tests** (extend `tests/test_videos_routes.py` or new `test_segments_routes.py`):
- `GET /segments` for a video with `tokens` populated → response includes the `tokens` field deserialised.
- `GET /segments` for a video with `tokens: null` → response includes `tokens: null`.

**Frontend** — same deferral as 013–016 (no new test infra here). Manual verification against a freshly processed video: tap a marked span, panel opens with live data, "Re-escuchar" seeks to the segment.

**Spike artefact**: captured in the eventual `018-token-level-transcript/decision.md` once the feature lands. No commit of spike scripts (matches 017's stance).

**Out of test scope**: real Claude calls in CI. Spike resolves the qualitative bar; CI tests use mocks.
