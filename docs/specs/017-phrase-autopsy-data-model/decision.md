# Decision: Phrase Autopsy data model + Claude generator (017)

| Field | Value |
|---|---|
| spec | [spec.md](./spec.md) |
| status | implemented |
| created | 2026-05-09 |
| branch | `feat/017-phase-autopsy-data-model` |

---

## What shipped

Two endpoints under `/api/videos`, cache-first, Spanish-only, write-once:

- `POST /api/videos/{video_id}/autopsy/explain` — body `{ phrase, start_time }`. Cache hit returns immediately; cache miss calls Claude (`claude-4-sonnet-20250514`) with the phrase + segments overlapping `start_time ± 6s`, persists, returns the row.
- `GET /api/videos/{video_id}/autopsy` — lists all cached rows for the video (empty list when none).

`video_id` in both URLs is the YouTube id; the response carries `video_id` as the YouTube id too (the DB id stays internal).

Cache key is `(video.id, normalize_phrase(phrase))` where `normalize_phrase` is `strip → collapse-whitespace → casefold`. Original casing is preserved on `phrase` for display.

Failure modes:
- 422 — empty phrase, phrase >200 chars, negative `start_time` (Pydantic `Field` constraints).
- 404 — unknown YouTube id.
- 502 — Claude call errored or returned malformed/invalid JSON. Nothing is persisted on 502.

## Files added / touched

Added:
- `src/services/phrase_autopsy.py` — `PhraseAutopsyService`, `AutopsyGenerationError`, `phrase_autopsy_service` singleton, the locked Spanish prompt (see below).
- `src/repositories/autopsy_repository.py` — `AutopsyRepository` and module-level `normalize_phrase`.
- `alembic/versions/929145c0af7d_add_phrase_autopsy_table.py` — migration.
- `tests/test_phrase_autopsy_service.py` — 11 service tests (mocked Anthropic client).
- `tests/test_autopsy_routes.py` — 13 route tests (cache hit/miss, two-casing dedup, 422/404/502, empty/populated GET, unique-constraint smoke).
- `scripts/spike_autopsy.py` — one-off spike runner. Not load-bearing; safe to delete.

Touched:
- `src/models/database.py` — added `PhraseAutopsy` table model and `phrase_autopsies` back-reference on `Video`. `__table_args__` carries the unique constraint.
- `src/models/schemas.py` — added `AutopsyGrammarRow`, `AutopsyExplainRequest`, `AutopsyEntryResponse`.
- `src/api/routes/videos.py` — added the two endpoints at the bottom of the router.
- `src/repositories/segments_repository.py` — added `context_around(video_id, t, window_seconds=6.0)`.
- `pyproject.toml` — added `phrase_autopsy.py` to the existing E501 per-file-ignore list (long-form Spanish prompts are content, not style).
- `docs/specs/017-phrase-autopsy-data-model/spec.md` — flipped `status: draft` → `status: approved` after the spike passed.

## Spike

Eight phrases × two runs each (16 total) ran through a draft prompt against `claude-4-sonnet-20250514` with synthesized 1–2-segment context.

| metric | result |
|---|---|
| `json.loads` success | 16 / 16 (100%) |
| Required-fields shape valid | 16 / 16 (100%) — register / grammar / natural_notes all present, correctly typed |
| `grammar[i].tag ≤ 25 chars` | 12 / 16 (75%) — all 4 misses were legitimate Spanish grammatical terminology that genuinely runs longer (`complemento circunstancial` 26, `interjección con subjuntivo` 27, `pretérito imperfecto continuo` 29, `pretérito indefinido puntual` 28) |
| Distinct tags within an output | 16 / 16 |
| `natural_notes` 2–4 entries, B2-readable, no English | 16 / 16 |
| Stable across reruns | yes — register slot occasionally varies (e.g. `coloquial · oral` vs `cotidiano · neutral` for `lo que pasa es que`), but both pickings are reasonable; tag wording shifts but the linguistic content is consistent |

**Decision from the spike**: relax the 25-char tag guidance in the prompt to "preferiblemente ≤25 caracteres, máximo 40", and do **not** validate tag length server-side. The 25-char ceiling was guidance to keep tags scan-friendly, not a hard contract; rejecting `pretérito imperfecto continuo` would mean fighting Spanish.

Sample outputs (good + borderline):

**Good** — `no me da igual`, run 1:
```json
{
  "register": "cotidiano · enfático",
  "grammar": [
    { "tag": "pronombre dativo", "text": "..." },
    { "tag": "verbo dar impersonal", "text": "..." },
    { "tag": "negación enfática", "text": "..." },
    { "tag": "expresión idiomática", "text": "..." }
  ],
  "natural_notes": [
    "Suena mucho más directo y emocional que decir 'me importa' o 'no me es indiferente'",
    "Es la respuesta perfecta cuando alguien asume que no te afecta algo que en realidad te molesta",
    "Se usa especialmente cuando quieres contradecir la idea de que eres indiferente o pasivo"
  ]
}
```

**Borderline** — `a eso de las nueve`, run 1:
```json
{
  "register": "cotidiano · neutral",
  "grammar": [
    { "tag": "locución prepositiva", "text": "..." },
    { "tag": "preposición temporal", "text": "..." },
    { "tag": "pronombre demostrativo", "text": "..." },
    { "tag": "complemento circunstancial", "text": "..." }
  ],
  "natural_notes": [...]
}
```
The `complemento circunstancial` tag is 26 chars — within the relaxed 40-char ceiling, fine. Notes were strong but a touch generic compared to the fixture.

Full results live in `scripts/spike_autopsy_results.json` (kept locally; not committed long-term).

## Locked prompt

Captured verbatim from `src/services/phrase_autopsy.py`. The format string takes `phrase` and `context_block` (one bullet per surrounding segment, or `"- (sin contexto adicional disponible)"` if the segment table is empty for the video and we fell back).

```
Eres un lingüista hispanohablante explicándole a una estudiante de español de
nivel B2 (Ana) por qué cierta frase de un vídeo le sonó natural pero no la pudo
analizar. Toda tu respuesta es en español. NO traduzcas al inglés. NO incluyas
campos de traducción ni "literal".

Devuelve EXCLUSIVAMENTE un JSON con esta forma exacta:

{
  "register": string,        // p. ej. "cotidiano · neutral", "formal · escrito", "coloquial · enfático"
  "grammar": [               // entre 2 y 5 entradas
    { "tag": string, "text": string }
  ],
  "natural_notes": [string]  // entre 2 y 4 observaciones cortas en español
}

Reglas:
- Cada `tag` es una etiqueta gramatical breve en español (preferiblemente
  ≤25 caracteres, máximo 40): «preposición», «subjuntivo de duda»,
  «pronombre dativo», «verbo impersonal», «discurso indirecto», etc. No
  repitas la misma etiqueta dos veces.
- Cada `text` es UNA sola frase en español que explica el papel de ese elemento
  en *esta* frase concreta — no una definición de manual.
- Cada `natural_notes` es una observación corta en español sobre por qué suena
  nativo, qué registro evoca, qué alternativa habría sido más rígida o menos
  idiomática, o cuándo NO lo dirías. Escribe a una persona B2: nada de jerga
  lingüística pesada, nada de tautologías («es natural porque suena natural»).
- No envuelvas el JSON en markdown. No añadas comentarios ni texto fuera del
  objeto JSON.

Frase a analizar:
«{phrase}»

Contexto inmediato del vídeo (segmentos cercanos, en orden):
{context_block}
```

Model id is `claude-4-sonnet-20250514` to match `services/questions.py` and `services/dialect_classifier.py`. Roadmap item 026 will sweep all three to current models in one pass.

## Schema as shipped

The shipped schema matches the spec exactly:

```python
class AutopsyEntryResponse(BaseModel):
    id: int
    video_id: str           # YouTube id
    phrase: str
    start_time: float
    register: str
    grammar: list[AutopsyGrammarRow]   # AutopsyGrammarRow = { tag: str, text: str }
    natural_notes: list[str]
    created_at: datetime
```

The frontend's existing `AutopsyEntry` type (`webapp/src/lib/autopsy-types.ts`) consumes a subset (`phrase`, `start_time`, `register`, `grammar`, `natural_notes`); the extras (`id`, `video_id`, `created_at`) are harmless to the panel. 018 will wire transcript taps to this endpoint and 016 will stop reading from `webapp/src/data/autopsy-fixtures.ts` at that point.

## Notable deltas from the proposed approach

- **Tag length cap**: spec proposed ≤25 chars (with a `(e.g. ...)` example). Spike showed 25% of generations exceed this for legitimate Spanish grammatical terminology. Resolution: the prompt asks for ≤25 chars as a preference and ≤40 as a ceiling; server-side validation does not enforce length. The frontend renders tags as small chip-style labels and handles wrapping naturally.
- **`register` field shadows a SQLModel/BaseModel parent attribute**: SQLModel and Pydantic emit a `UserWarning` because `register` is a method on the metaclass / parent class. We verified read/write of the field works correctly (instance dict wins over class methods on attribute access) and accepted the warning rather than renaming. The frontend, the spec, and the existing fixture all use `register`; bending it server-side would have created a translation layer for nothing.
- **Context fallback**: spec said "if the segments table is empty for this video, return `[full_transcript]` as a fallback so the endpoint still works on legacy rows". We put this fallback at the **route layer** rather than inside `SegmentsRepository.context_around`, because the repo doesn't otherwise depend on `Video` and we didn't want to widen its surface for one edge case.
- **Test layout**: spec proposed `tests/services/test_phrase_autopsy.py` and `tests/api/test_autopsy_routes.py`. The repo's existing test layout is flat (no subdirectories under `tests/`), so we followed that convention with `tests/test_phrase_autopsy_service.py` and `tests/test_autopsy_routes.py`.

## Test surface

41 tests pass (24 new for 017 + 17 pre-existing). Coverage summary:

Service (`tests/test_phrase_autopsy_service.py` — 11 tests):
- Valid JSON → parsed payload.
- Markdown-fenced JSON → unwrapped and parsed.
- Malformed JSON → `AutopsyGenerationError`.
- Missing `register` / empty `grammar` / `grammar[i].text` missing → `AutopsyGenerationError`.
- Anthropic SDK error wrapped → `AutopsyGenerationError`.
- Prompt includes phrase + each context segment verbatim.
- Empty context falls back to a sentinel line in the prompt.
- Locked model id sent in the request.

Routes (`tests/test_autopsy_routes.py` — 13 tests):
- Cache miss calls service exactly once, persists, response shape matches.
- Cache hit returns same id without calling service.
- Two casings of the same phrase share one row; original casing preserved.
- Empty / >200-char phrase → 422.
- Negative `start_time` → 422.
- Unknown YouTube id (POST and GET) → 404.
- Service raises → 502 with Spanish detail; nothing persisted.
- No segments for video → fallback to `video.transcript`.
- GET empty list when no rows.
- GET returns all rows.
- Unique-constraint smoke (direct DB insert with same `phrase_key` raises `IntegrityError`).

CI commands: `uv run pytest -q` and `uv run ruff check src/ tests/` both clean.

## Out of scope (still)

Per the spec's Non-Goals, none of the following landed:
- Pre-generation during `process_video_flow`.
- `PATCH`/`DELETE` on autopsy rows.
- Cache TTL / invalidation.
- English `natural` / `literal` fields (permanent product position).
- Quality / confidence scoring.
- Token-level transcript or wiring transcript taps to the new endpoint — 018.
- Cross-video autopsy cache.
- Model refresh — 026.

016's frontend remains on its hand-written fixture (`webapp/src/data/autopsy-fixtures.ts`) until 018 ships tappable transcript words.
