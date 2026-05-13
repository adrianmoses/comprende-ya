# Decision Record: Token-level transcript with phrase-span markers

| Field | Value |
|---|---|
| id | 018 |
| status | implemented |
| created | 2026-05-10 |
| spec | [spec.md](./spec.md) |
| branch | `feat/018-token-level-transcript` |

---

## Context

016 shipped the autopsy panel against a fixture (`webapp/src/data/autopsy-fixtures.ts`) with a temporary "Frases destacadas" rail trigger. 017 shipped the autopsy endpoint + cache table. 018 is the connector that wires the transcript itself to that endpoint, deletes the fixture, and pre-populates the cache so taps feel instant.

The implementation landed essentially as the spec described — JSON `tokens` column on `VideoSegment`, one Claude call per video at flow time produces marker spans + autopsy payloads, spaCy reconciles span phrases against segment tokens, frontend renders tappable runs. Two surprises during implementation:

1. **The "spike" became the backfill.** The spec called for a one-off uncommitted spike script to validate prompt quality against `m1DFpkNdcv0` + a fresh video. In practice the only video in the dev DB (`m1DFpkNdcv0`) was processed pre-018 so it had no `tokens`, which made the feature un-testable in the UI. A backfill script that runs *only* the marker step against an existing video solved both problems at once: it produced the spike evidence (real Claude output, real contiguity rate) AND made the existing video visibly tappable. Spec listed "backfill of existing videos" as a Non-Goal; we added it anyway because the alternative (reprocess the entire video, paying for Whisper + question regen) was strictly worse.
2. **The shared spaCy singleton stayed half-shared.** The plan called for hoisting `nlp` into a shared module so both `frase_exercise_generator` and the new marker save task use the same instance. We extracted `src/services/spanish_nlp.py` and the new code consumes it, but `FraseExerciseGeneratorService` still loads its own model — refactoring it is out of scope for 018 and noted under 026.

## Decision

Ship `tokens: Optional[str]` (JSON) on `VideoSegment`, a `PhraseMarkersService` that asks Claude (one call per video) for 5–15 phrase markers + per-marker autopsy payloads, a pure `tokenize_segment(text, span_phrases, nlp)` helper that walks spaCy tokens and assigns `span` indices via casefold + accent-strip matching, two new Prefect tasks between `save_video_segments` and `generate_exercises_task`, and an additive `tokens` field on `GET /api/videos/{video_id}/segments`. Frontend wraps contiguous span runs in a `.tx-span` button that calls `POST /autopsy/explain` on tap. Marker generation failure is non-fatal — segments stay tappable-less, exercises ship as before. Pre-warm uses get-then-create (existing rows win) instead of `INSERT … ON CONFLICT DO NOTHING` SQL because `AutopsyRepository.create` already commits per row at the application level.

A reusable `scripts/backfill_phrase_markers.py` runs the marker step against any pre-018 video without re-downloading or re-transcribing.

---

## Alternatives Considered

### Where to store the per-segment token list

**Option A:** JSON column on `VideoSegment` (chosen).
- Pros: tokens are read every time the segment is read, never queried independently or indexed; matches access shape; no join.
- Cons: stringly-typed JSON; schema drift risk if the shape changes.

**Option B:** New `VideoToken` table with one row per token, FK to `VideoSegment`.
- Pros: each token is queryable; type-checked at the row level.
- Cons: adds a join for zero benefit (we never query individual tokens); inflates row count by 10–20× per segment.

**Chosen:** A. Spec already proposed this; implementation reaffirmed it.

### How to localise marker spans inside segment text

**Option A:** Casefold + Unicode NFKD accent-strip for *matching only*; keep original casing in storage; silently drop non-contiguous matches (chosen).
- Pros: tolerates Claude's casing/accent jitter without warping the displayed text; graceful degradation matches the spec's "skip the span, log it, keep going" stance.
- Cons: still misses on punctuation-inside-phrase, abbreviations, or wholly-fabricated phrases.

**Option B:** Ask Claude for character offsets `(start, end)` instead of `tokens_in_segment`.
- Pros: deterministic localisation; no token-alignment work.
- Cons: Claude is poor at counting characters; would need verification anyway; couples the prompt to Whisper's exact whitespace handling.

**Option C:** Fuzzy matching (Levenshtein over token windows).
- Pros: catches near-misses Claude's exact tokens drift on.
- Cons: adds a similarity threshold to tune; risks promoting wrong phrases as "located"; the live spike showed 14/15 = 93% with the simple matcher, so the cost-to-fix isn't justified.

**Chosen:** A. Live spike's contiguity rate (93%) cleared the spec's 80% bar with margin.

### How to pre-warm `phrase_autopsy` (avoid duplicates)

**Option A:** Application-level `get_by_phrase` check before `create` (chosen).
- Pros: matches `AutopsyRepository`'s commit-per-row pattern; no SQL surface change; readable in Python.
- Cons: TOCTOU between check and insert (acceptable — single-writer flow, no concurrent processing of the same video).

**Option B:** Raw SQL `INSERT … ON CONFLICT (video_id, phrase_key) DO NOTHING`.
- Pros: atomic; single round-trip per row.
- Cons: requires bypassing the repository to issue raw SQL, or adding a new repo method that does so; the spec said "ON CONFLICT DO NOTHING" but really meant the *semantic*, not the SQL clause.

**Chosen:** A.

### `nlp` model loading: shared singleton vs per-service load

**Option A:** Extract `src/services/spanish_nlp.py` with a lazy lock-protected `get_nlp()` and have new code consume it; leave `FraseExerciseGeneratorService` on its own load (chosen).
- Pros: solves the immediate problem (the marker save task doesn't double-load the transformer); minimal change footprint.
- Cons: one model still gets loaded twice in production (when both 007 and 018 paths run for the same flow). Memory cost: one `es_dep_news_trf` instance (~500MB).

**Option B:** Refactor `FraseExerciseGeneratorService` to consume `get_nlp()` in this PR.
- Pros: one transformer load per process.
- Cons: out of scope for 018; the refactor risks regressing 007's exercise generation; better as a focused commit under 026.

**Chosen:** A. TODO captured for 026.

### How to make the existing seeded video testable

**Option A:** Backfill script that runs only the marker step against an existing video (chosen, committed at `scripts/backfill_phrase_markers.py`).
- Pros: one Claude call (~10¢); zero re-transcription cost; reusable for future pre-018 videos; doubles as the spike artefact.
- Cons: spec listed "backfill of existing videos" as a Non-Goal; we're carrying a script the spec said wasn't needed.

**Option B:** Reprocess `m1DFpkNdcv0` end-to-end via `process_video_flow(force=True)`.
- Pros: exercises the full new flow path (real proof-of-correctness).
- Cons: re-pays for Whisper transcription + question regeneration + exercise regeneration; deletes and recreates `Question` rows the user has progress against; ~10× the cost and runtime.

**Option C:** Accept that only freshly-processed videos see spans, document it, move on.
- Pros: cheapest.
- Cons: nothing in the dev DB is freshly-processed; no path to manual QA without spending money on a new video.

**Chosen:** A. The Non-Goal stands for the *production* pipeline (no auto-backfill at deploy time); the script is a developer tool.

### Test file layout

**Option A:** Standalone `tests/test_segments_routes.py` for the `/segments` shape tests (chosen).
- Pros: matches 017's split (`test_phrase_autopsy_service.py` + `test_autopsy_routes.py`); easier to find.
- Cons: small file (2 tests).

**Option B:** Extend `tests/test_videos_routes.py` with the segments cases.
- Pros: fewer files.
- Cons: mixes the videos-list/status surface with the segments surface.

**Chosen:** A.

---

## Tradeoffs

The chosen approach optimises for **graceful degradation everywhere** at the cost of silent failure modes:

- A non-contiguous span is dropped without surfacing to the user — the only way to know is to read `logger.warning` lines from the worker. For a bare-bones B2 learner using the product solo, this is right; for an editorial QA pass before sharing the product, we'd want a per-video "missing markers" report.
- Marker generation failure leaves `tokens: null` and an unpopulated cache. The frontend falls back to plain text — Ana can't tell the difference between "this video has no markers because Claude failed" and "this video genuinely has nothing worth tapping". Acceptable for now; a "regenerate markers" admin endpoint would let editors recover without reprocessing the whole video. Out of scope for 018.
- One Claude call per video (vs per segment) makes marker selection holistic but means we can't retry just one segment's worth of markers. A bad full-transcript output forces a full re-call.
- Pre-warming via per-row commit (`AutopsyRepository.create` commits each call) means a partial failure during pre-warm leaves N/M rows persisted, with no transactional rollback. For a write-once cache where every row is independently valid, this is fine. Flagged for 026 cleanup.
- We accept the second spaCy model load (007 + 018 paths each load one) as a one-PR scope concession.

What we gave up by NOT asking Claude for character offsets: deterministic span localisation. What we gained: prompt simplicity + alignment with how 017 already talks to Claude (text in, text out, no positional bookkeeping).

---

## Spec Divergence

| Spec said | What was built | Reason |
|---|---|---|
| "Backfill of existing videos" is a Non-Goal | Committed `scripts/backfill_phrase_markers.py` as a dev tool | Without it, the only video in the dev DB couldn't be tested in the UI without paying for a full reprocess. The Non-Goal still stands for the production pipeline (no auto-backfill at deploy time). |
| Spike script "not committed; matches 017's stance" | Spike was the backfill (committed) | Combining the two avoided burning a separate ~10¢ Claude call. The "spike artefact" the spec wanted is captured below under Test Evidence. |
| Flow loads spaCy once and passes the `nlp` object to both consumers | New `src/services/spanish_nlp.py` with `get_nlp()` lazy singleton; only the marker save task consumes it; `FraseExerciseGeneratorService` still loads its own model | Refactoring `FraseExerciseGeneratorService` to consume `get_nlp()` would touch 007's exercise generation; risk-vs-scope said defer to 026. |
| `INSERT … ON CONFLICT DO NOTHING` for autopsy pre-warm | App-level `get_by_phrase` check before `create()` | `AutopsyRepository.create` commits per row; matching that pattern is cleaner than dropping to raw SQL. The semantic ("existing rows win") matches. |
| Extend `tests/test_videos_routes.py` with `/segments` cases | New `tests/test_segments_routes.py` | Matches the 017 split convention; one file per route domain. |
| `tests/test_video_processing_markers.py` covers 3 cases (success, service-raises, conflict-skip) | 5 cases (added: empty markers list path; nlp + db_session both patched via autouse) | Same coverage scope; extra fixtures came from running the tests against a real session and finding two more guardrails worth pinning. |

No spec acceptance criterion was dropped or weakened.

---

## Spec Gaps Exposed

1. **No production observability for "marker generation succeeded but Claude attached the phrase to the wrong segment".** The live spike found 1/15 markers (`«dar a luz»` on seg 5, where the actual segment text is `Afirmaba haber sido una mujer llamada Luji Devi`) silently dropped by the contiguity check. The flow logged it, the user never knows. A "marker localisation rate" emitted to the flow's status (or to `processing_jobs.notes`) would let editorial QA spot prompt drift over time. Candidate for 022 (KPI work) or a dedicated 027.
2. **The "Re-escuchar" button on the autopsy panel doesn't have a defined target.** The current implementation seeks to the autopsy row's `start_time` (the segment's start). The spec implied this but didn't pin it; for a single-word span at the end of a long segment, "re-escuchar" replays the entire segment. Acceptable for now, but if word-level Whisper timestamps land later, this is the spot to upgrade.
3. **No path back to the autopsy panel from the saved-phrases (Mis frases) view of 020.** The spec didn't address it. 020's design needs to decide whether tapping a saved phrase re-opens the cached autopsy or just seeks the video. Out of scope here, flagged for 020.

---

## Test Evidence

```
$ uv run pytest tests/test_phrase_markers_service.py tests/test_segment_tokenizer.py tests/test_video_processing_markers.py tests/test_segments_routes.py -v
============================= test session starts ==============================
platform darwin -- Python 3.12.2, pytest-9.0.3, pluggy-1.6.0
collected 28 items

tests/test_phrase_markers_service.py ..........                          [ 35%]
tests/test_segment_tokenizer.py ...........                              [ 75%]
tests/test_video_processing_markers.py .....                             [ 92%]
tests/test_segments_routes.py ..                                         [100%]

======================= 28 passed, 44 warnings in 5.95s ========================
```

Full suite (69 tests including pre-018):

```
$ uv run pytest
======================= 69 passed, 143 warnings in 8.03s =======================
```

Quality gates:

```
$ uv run ruff check && uv run ruff format --check
All checks passed!
54 files already formatted

$ cd webapp && pnpm typecheck
> tsc --noEmit
(no output)

$ cd webapp && pnpm lint
> biome check
Checked 24 files in 51ms. No fixes applied.
```

### Live spike against `m1DFpkNdcv0` (369 segments, REENCARNACIÓN)

Run via `uv run python scripts/backfill_phrase_markers.py 1`. One Claude call (`claude-4-sonnet-20250514`), MAX_TOKENS=4000.

| metric | result |
|---|---|
| Markers returned by Claude | 15 / 15 (hit the spec's MAX_MARKERS upper bound) |
| Per-entry payload validation | 15 / 15 passed `_validate_marker` |
| Spans located contiguously in the named segment | 14 / 15 = **93.3%** (well above the spec's ≥80% bar) |
| Phrases 1–6 words | 15 / 15 |
| Spanish-only, no English crutches | 15 / 15 |
| Duplicate phrases | 0 |
| Autopsy rows pre-warmed | 15 (1 of which already existed from manual testing — skipped) |

The single localisation miss: Claude attached `«dar a luz»` to segment 5, but segment 5's text is `Afirmaba haber sido una mujer llamada Luji Devi` — the phrase doesn't appear. The tokenizer correctly dropped it; the flow continued; the autopsy row was still inserted (it's keyed by phrase, not by segment) so a manual tap on that phrase elsewhere would still hit the cache. Behavior matches spec.

Sample marker output (good — `seg 1`, `«A finales de los años 30»`):

```json
{
  "phrase": "A finales de los años 30",
  "segment_number": 1,
  "tokens_in_segment": ["A", "finales", "de", "los", "años", "30"],
  "register": "narrativo · formal"
}
```

Persisted token list for segment 1 (showing the span markup):

```json
[
  {"t": "A", "span": 0, "start": true},
  {"t": "finales", "span": 0},
  {"t": "de", "span": 0},
  {"t": "los", "span": 0},
  {"t": "años", "span": 0},
  {"t": "30", "span": 0},
  {"p": ","},
  {"t": "en"},
  ...
]
```

Editorial pick selection (the 15 returned phrases, abbreviated):

```
seg   1 · narrativo · formal      · A finales de los años 30
seg   3 · narrativo · formal      · Se trataba de Shanti Devi
seg   5 · médico · neutro         · dar a luz                          [dropped — segment mismatch]
seg   6 · descriptivo · neutro    · a más de 130 kilómetros de distancia
seg  11 · periodístico · neutro   · llegó a los periódicos
seg  15 · narrativo · neutro      · sin decirle dónde iba
seg  20 · descriptivo · neutro    · con total naturalidad
seg  30 · académico · formal      · no pudo ser descartado con facilidad
seg  41 · psicológico · cotidiano · pensaron que era una fase
seg  49 · argumentativo · formal  · aún así
seg  56 · testimonial · dramático · así fue como morí
seg  69 · infantil · emotivo      · ahora tengo dos mamás
seg  86 · académico · impersonal  · se han comentado cientos de casos
seg  87 · académico · formal      · desafiando cualquier explicación racional
seg  97 · temporal · formal       · a lo largo de los años
```

Editorial read: solid B2 picks — a healthy mix of narrative/temporal markers (`a lo largo de los años`, `aún así`), idioms (`con total naturalidad`, `dar a luz`), and emotionally-marked register switches (`ahora tengo dos mamás`, `así fue como morí`). Not worth re-prompting; these are exactly the spans Ana should be tapping.

### Backfill script

Reusable: `uv run python scripts/backfill_phrase_markers.py <video_db_id>` (or `--youtube-id`, or `--dry-run`). Wraps the same logic as `save_phrase_markers_task` but runs standalone — no Whisper, no question regen, no exercise regen, ~one Claude call per invocation. Exists at `scripts/backfill_phrase_markers.py`.

Usage during dev:

```
$ uv run python scripts/backfill_phrase_markers.py 1
📥 Cargando segmentos para video_id=1…
✅ 369 segmentos cargados
🤖 Llamando a Claude para generar marcadores… (puede tardar ~10–30 s)
✅ 15 marcadores devueltos:
   - seg   1: «A finales de los años 30» — narrativo · formal
   - seg   3: «Se trataba de Shanti Devi» — narrativo · formal
   ...
💾 Tokenizando segmentos y persistiendo…
✅ tokens escritos en 369 segmentos
✅ 15 filas pre-pobladas en phrase_autopsy
```
