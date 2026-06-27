# Decision Record: Speaking-prompt audio recordings

| Field | Value |
|---|---|
| id | 021 |
| status | implemented |
| created | 2026-06-27 |
| spec | [spec.md](./spec.md) |

---

## Context

019/020 shipped the chunk library with rotating speaking prompts but no way to
capture the learner speaking them — `ChunkCard.tsx`'s "Grabar respuesta" button
was a 3.5s `setTimeout` stub (`REC_STUB_MS`) recording no audio. 021 closes that
loop: record a take against a saved chunk, persist it, replay it.

This deliverable is **scoped to validation + backend only** (per the approved
plan, `feat/021-speaking-prompt-recordings`). The frontend cutover — replacing
the stub with real `MediaRecorder` capture and a playback control — is a
deliberate follow-up, not part of this record. The split was driven by the
spec's one Medium-confidence risk: whether the browser's recorded audio plays
back as-stored without transcoding (OQ1). It made no sense to invest in UI before
that question was settled, so the plan front-loaded a throwaway spike to answer
it, then built the backend behind it.

Two things surfaced during implementation that shaped the work beyond the spec:

1. **`alembic revision --autogenerate` pulled in unrelated schema drift.** The
   autogenerate diff against the live Postgres DB detected ~8 changes on
   `answer_progress`, `frase_exercise`, and `processing_jobs` (FK re-creations,
   a `TEXT → AutoString` type change, index additions) that have nothing to do
   with this feature — pre-existing drift between the models and the database.
   The generated migration was hand-stripped to only the `recordings` table.

2. **The migration wasn't applied to the dev DB until the spike forced it.** The
   migration was verified on a throwaway SQLite DB but not run against the
   operator's Postgres until a `relation "recordings" does not exist` error
   during the manual spike. Applied then; noted as a process gap below.

## Decision

Recordings are stored on the **filesystem** (`recordings/` dir, sibling of
`temp/`, durable rather than transient) with a `recordings` table holding the
path + metadata — **one row per chunk, unique on `chunk_id`, overwrite on
re-record**. Three routes were added to the existing chunks router
(`POST`/`GET`/`DELETE /api/chunks/{id}/recording`), the chunk-delete path now
unlinks the audio file before the row cascades away, and `ChunkResponse` gained
`has_recording` via `selectinload(Chunk.recording)` so the card knows to render a
playback control without an N+1.

Filesystem paths are **server-generated** (`uuid4().hex` + extension derived from
the content-type) and stored on the row; the route never builds a path from user
input, so traversal is impossible by construction. Bytes are stored exactly as
received and served back unchanged — no server-side transcoding — which OQ1's
spike validated as safe.

**The OQ1 gate passed.** `MediaRecorder` emits `audio/webm;codecs=opus` on
Chrome/darwin; those bytes round-trip through `POST` → disk → `GET` →
`<audio>` and play back with no conversion. The Medium-confidence risk is
retired; the spec's documented fallback (pin a `mimeType`) was not needed.

---

## Alternatives Considered

### Storage substrate (the spec's primary decision)

**Option A — Filesystem + DB path.** Bytes on disk under `RECORDINGS_DIR`, path
+ metadata on a `recordings` row.
- Pros: DB stays lean (audio never travels through SQL); mirrors the existing
  `temp/` pattern; no new infra.
- Cons: route owns file lifecycle (orphan-cleanup on overwrite/delete); DB backup
  no longer captures the audio.

**Option B — DB blob (bytea).** Audio bytes in a column.
- Pros: one backup story; no orphan files; no path management.
- Cons: DB bloat; large blobs over SQL; awkward streaming.

**Option C — Object storage (S3/MinIO).** Upload to a bucket, store the key.
- Pros: scales, production-ready.
- Cons: a dependency + config the single-user local stack doesn't have.

**Chosen:** A, as specced. Single-user, single-process — filesystem is the
honest fit; B's bloat and C's premature infra both lose. The orphan-cleanup cost
is contained to two delete paths.

### Cardinality — one per chunk vs history

**Option A — One recording per chunk, overwrite (`chunk_id` unique).**
- Pros: matches the single rec-button in the design; no history UI; bounded
  storage; the unique constraint makes overwrite the only possible semantics.
- Cons: re-recording destroys the prior take.

**Option B — Take history (many per chunk).**
- Pros: hear progress over time.
- Cons: list/delete-take UI; unbounded growth; no mastery signal yet to justify
  it.

**Chosen:** A, as specced. The unique FK forecloses history deliberately; if
"progress over time" is ever wanted it's a separate spec.

### File-deletion ownership — repository vs route

**Option A — Repositories stay row-only; routes orchestrate file deletion via
`recording_storage`.**
- Pros: repos remain storage-agnostic (testable without a filesystem); the two
  delete paths (recording-delete, chunk-delete) both call the same helper
  explicitly, so the coupling is visible.
- Cons: file-cleanup logic lives in two route handlers, not one repo method.

**Option B — `ChunkRepository.delete` / `RecordingRepository.delete` remove the
file as a side effect.**
- Pros: one call does everything.
- Cons: repos become filesystem-aware; harder to unit-test; hidden side effects.

**Chosen:** A. The DB cascade (`cascade="all, delete-orphan"` + FK
`ondelete=CASCADE`) handles the *row* on chunk-delete; only the *file* needs
explicit removal, done in the route before the cascade fires. Keeps the
repository layer pure, consistent with how the rest of the codebase separates
persistence from external effects.

### Upload size guard

**Option A — Read the upload fully, reject over a byte cap (`413`).** Cap at
10 MB (`MAX_RECORDING_BYTES`).
- Pros: simple; generous for a phrase-length opus take; no streaming complexity.
- Cons: a malicious huge upload is read into memory before rejection.

**Option B — Stream + enforce `Content-Length` before reading.**
- Pros: rejects before buffering.
- Cons: `Content-Length` is client-controlled and spoofable; more code for a
  single-user local tool.

**Chosen:** A. At single-user scale the in-memory read of a capped upload is a
non-issue; the cap exists to stop a runaway recording, not to harden against an
adversary.

---

## Tradeoffs

What the chosen approach optimises for, and what it gives up:

- **Durable filesystem storage over a transient/DB substrate.** Recordings
  survive restart (unlike `temp/`, cleaned per-flow) and keep the DB lean. Cost:
  audio lives outside the database, so a DB-only backup misses it, and the two
  delete paths must explicitly unlink files to avoid orphans. The `recordings/`
  dir is git/docker-ignored.
- **`has_recording` boolean on the list, not the recording metadata.** The card
  only needs "is there a take?" to decide whether to show playback; the full
  `RecordingResponse` (size, duration, content-type) is fetched lazily if ever
  needed. Cost: a second round-trip if the card later wants metadata — but it
  doesn't today, and the boolean keeps `GET /api/chunks` cheap and a single
  query (`selectinload`, no N+1).
- **Store-as-received, serve-as-is.** No server-side transcoding keeps the
  backend a dumb store and sidesteps an ffmpeg-in-the-request-path dependency.
  Cost: relies on the recording browser and playback browser agreeing on format
  — safe under the single-user assumption (same browser both ends), and OQ1
  confirmed it. Cross-browser playback (record in Chrome, play in Safari) is
  explicitly out of scope.
- **Content-type-driven file extension via a small explicit map.** `_EXT_BY_TYPE`
  covers `audio/webm|mp4|mpeg|ogg|wav`; anything else falls back to `.bin`.
  Cost: an exotic recorder MIME lands as `.bin` — harmless (the stored
  `content_type` drives playback, not the extension), but worth knowing the
  extension is cosmetic, not authoritative.

---

### Spec Divergence

The implementation matched the spec's approach faithfully. The acceptance
criteria split cleanly into backend (delivered here) and frontend (deferred by
the plan). Open questions resolved as anticipated. Minor as-built specifics:

| Spec Said | What Was Built | Reason |
|---|---|---|
| `recordings` table with `file_path` storing a "relative path" (OQ3 "leaning" path-on-row, non-guessable name) | `file_path` stores just the `uuid4().hex` + extension *filename* (relative to `RECORDINGS_DIR`), resolved via `recording_storage.abs_path()` | Storing the bare filename (not a multi-segment path) is the simplest form of the path-on-row decision and keeps the traversal-safe property — the dir comes from config, never the row or the request. |
| Frontend cutover (card capture, playback, permission-denied UI, `["chunks"]` invalidation, client max-duration) listed in spec Acceptance Criteria | Not built in this deliverable | The approved plan scoped this round to validation + backend; the frontend is the next plan, now unblocked by the passed gate. Not a divergence from intent — a planned phase split. |
| OQ1 validation framed as a frontend-style spike | Validated in two halves: backend round-trip proven programmatically (real ffmpeg opus/webm, byte-identical); browser playback proven via a throwaway same-origin `/spike` page, then deleted | The agent can't drive a microphone; splitting the gate let the byte-path be machine-verified and left only the human-in-the-loop playback for the operator. |
| OQ2 backend size cap "~10 MB" | `MAX_RECORDING_BYTES = 10 * 1024 * 1024`, `413` over cap | As specced; exact value locked. Client-side max-duration auto-stop stays a frontend concern. |

---

## Spec Gaps Exposed

1. **Migration application is not part of the spec/plan's definition of done.**
   The migration was verified on disposable SQLite but never applied to the
   operator's Postgres until a runtime `relation "recordings" does not exist`
   error during the spike. The plan's verification section covered
   upgrade/downgrade *correctness* but not *"applied to the running dev DB."*
   Future plans touching schema should make "ran `alembic upgrade head` against
   the dev DB" an explicit step, since the manual gate (and the eventual
   frontend) run against Postgres, not the test SQLite.

2. **`alembic autogenerate` drift is a latent footgun for every future
   migration.** The autogenerate diff surfaced ~8 unrelated changes
   (`answer_progress`/`frase_exercise`/`processing_jobs` FK re-creations, a
   `TEXT → AutoString` type change). This means the models and the live DB schema
   have drifted, and every future autogenerate will re-propose these until
   reconciled. Candidate for a dedicated cleanup roadmap item: either a
   reconciling migration or a decision to accept the drift and teach autogenerate
   to ignore it. Not fixed here to keep 021 scoped.

3. **`config.py` eager API-key validation bites non-server entry points.** Every
   ad-hoc script that imports anything under `src/` (the spike-adjacent storage
   round-trip check, the DB-inspection one-liners) must export
   `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `YOUTUBE_API_KEY` or `config.py`
   raises at import. Already flagged in OVERVIEW audit notes; 021 is one more data
   point that lazy validation would help. Out of scope here.

---

## Test Evidence

New recording route tests — 11 cases covering every backend acceptance criterion
(create, overwrite-keeps-one-row, 404 on missing chunk, 413 over cap, GET
byte-equality + content-type, GET/DELETE 404s, `has_recording` flag, chunk-delete
cascade leaves no orphan file, stored path stays under `RECORDINGS_DIR`):

```
$ uv run pytest tests/test_recording_routes.py
11 passed in 5.60s
```

Full suite — no regression against the prior 102 (now 113 with the 11 new):

```
$ uv run pytest
113 passed in 7.97s
```

Lint + format clean:

```
$ uv run ruff check src/ tests/
All checks passed!
$ uv run ruff format --check src/ tests/
51 files already formatted
```

Migration round-trips on SQLite (the test engine):

```
$ alembic upgrade head     # fc80c83e59fe -> 2d4fe8532538, add recordings table
$ alembic downgrade -1     # 2d4fe8532538 -> fc80c83e59fe (recordings dropped)
```

Migration applied to the dev Postgres DB; `recordings` table confirmed present.

OQ1 validation gate — real `audio/webm;codecs=opus` (ffmpeg-generated, 9981
bytes) round-trips byte-identical through `recording_storage` with the correct
`.webm` extension; browser-recorded audio (151958 bytes, `audio/webm;codecs=opus`)
uploaded via `POST` and played back from `GET` through an `<audio>` element with
no transcoding. **Gate passed.** The throwaway `/spike` route + page were removed
after validation.
</content>
