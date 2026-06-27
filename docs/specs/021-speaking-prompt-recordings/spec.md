# Spec: Speaking-prompt audio recordings

| Field | Value |
|---|---|
| id | 021 |
| status | approved |
| created | 2026-06-27 |

---

## Why <!-- required -->

The chunk library (019/020) saves phrases with 2–4 rotating speaking prompts
(*consignas*) that invite the learner to produce the phrase out loud in new
contexts. But the invitation has no follow-through: when Ana speaks, nothing
captures it. The practice loop dead-ends at the prompt. There is no artifact of
her own production and no way to hear herself back.

This feature closes that loop: record a take against a saved chunk, persist it,
and play it back later from the Mis frases card. Speaking practice gains a
record and a playback — the minimum needed to make the *consignas* more than
decorative.

The 020 frontend already ships the affordance as a visual stub: `ChunkCard.tsx`
has a "Grabar respuesta" button that runs a 3.5s `setTimeout` and captures no
audio (`REC_STUB_MS`, marked `próximamente`). 021 makes it real.

### Consumer Impact <!-- required -->

The single B2 self-study learner ("Ana", per OVERVIEW). She taps **Grabar
respuesta** on a chunk card, speaks the prompt, stops, and can replay her take.
Re-recording overwrites the previous take. The benefit is self-monitoring —
hearing her own production against the prompt — not external feedback. There is
no scoring, no transcription, no correction (see Non-Goals); the value is the
learner's own ear on her own voice.

### Roadmap Fit <!-- required -->

Direct successor to 019 (chunk backend) + 020 (chunk frontend). 020 shipped the
recording button as an honest stub specifically anticipating this feature; its
decision record names the cutover as "a handler swap." The `recordings` write
endpoint was pre-declared in `ARCHITECTURE.md` ("Planned: frontend data flow",
`POST /api/chunks/{id}/recording`). 021 depends on 019's `chunks` table and the
`["chunks"]` query infrastructure from 020. It does **not** depend on 022
(profile/streak/KPIs) or any mastery signal — recordings here carry no
evaluation, so they unblock nothing in that direction and need nothing from it.

---

## What <!-- required -->

### Acceptance Criteria <!-- required -->

From the consumer's perspective:

- [ ] On a Mis frases chunk card, Ana can press **Grabar respuesta**, speak, and
  press again to stop. The button reflects live recording state (existing
  `is-recording` styling), driven by real microphone capture, not a timer.
- [ ] After stopping, the recording is uploaded and persisted server-side. The
  card shows a **playback control** for the saved take.
- [ ] Reloading the page (or revisiting Mis frases) still shows the playback
  control for any chunk that has a recording — recordings survive restarts.
- [ ] Pressing play replays Ana's own audio through the browser without
  transcoding or a download step.
- [ ] Re-recording a chunk that already has a take **overwrites** it: the old
  audio file is removed and the new one replaces it. Exactly one recording per
  chunk.
- [ ] Ana can delete a recording from the card, returning it to the
  no-recording state.
- [ ] If the browser denies microphone permission (or `MediaRecorder` is
  unavailable), the card surfaces a clear Spanish message and stays usable; no
  silent failure, no broken button.
- [ ] Deleting a chunk (existing `DELETE /api/chunks/{id}`) also removes its
  recording row and file — no orphaned audio on disk.

Backend contract:

- [ ] `POST /api/chunks/{chunk_id}/recording` accepts an audio upload
  (multipart), writes the bytes to a `recordings/` file, upserts a `recordings`
  row keyed unique on `chunk_id`, and returns recording metadata. 404 if the
  chunk does not exist.
- [ ] `GET /api/chunks/{chunk_id}/recording` streams the stored audio with the
  correct `Content-Type`. 404 if the chunk has no recording.
- [ ] `DELETE /api/chunks/{chunk_id}/recording` removes the row and the file,
  returns 204. 404 if absent.
- [ ] `GET /api/chunks` (list) gains a `has_recording: bool` field so the card
  knows whether to render the playback control without an extra round-trip per
  card.

### Non-Goals <!-- required -->

- **No ASR / pronunciation scoring / feedback of any kind.** Recordings are for
  personal re-listening only. This is the permanent OVERVIEW non-goal ("No audio
  evaluation"), not a deferral.
- **No transcription** of the recorded audio.
- **No waveform visualization, no trimming, no editing.** Record, stop, play,
  delete — nothing more.
- **No take history / multiple takes per chunk.** One recording per chunk,
  overwrite-on-re-record. (If a "hear your progress over time" feature is ever
  wanted, it is a separate spec; the `recordings` table's unique-on-`chunk_id`
  constraint deliberately forecloses it for now.)
- **No mastery signal derived from recordings.** No `mastery` column lands here;
  the design's mastery dots stay a `próximamente` stub.
- **No object storage / CDN / cloud upload.** Local filesystem only, matching the
  single-user single-process deploy.
- **No multi-user / per-user scoping.** Single-user, consistent with the rest of
  the backend.
- **No audio format conversion server-side.** Bytes are stored as received and
  served back as-is.

### Open Questions <!-- optional -->

1. **`MediaRecorder` MIME type across the stored bytes.** Chrome on darwin emits
   `audio/webm;codecs=opus`; Safari emits `audio/mp4`. The server stores
   whatever it receives and records the `content_type` on the row so playback
   sends the right header. **Resolved approach:** store the client-reported
   content type, default file extension off it; do not assume webm. Confirm in
   the spike that the stored blob round-trips to a playable `<audio>` on the same
   browser that recorded it. (Cross-browser playback — record in Chrome, play in
   Safari — is out of scope: single-user, single-browser assumption.)
2. **Max recording size / duration guard.** A runaway recording shouldn't write
   an unbounded file. **Deferred with default:** add a soft cap (e.g. reject
   uploads over ~10 MB — generous for a phrase-length take at opus bitrates) and
   a client-side max-duration auto-stop (e.g. 30s). Exact numbers settle during
   implementation; the cap exists, the value is tunable.
3. **Filename scheme.** `recordings/{chunk_id}.{ext}` (overwrite-friendly, one
   file per chunk) vs a uuid name with the path stored on the row. **Leaning:**
   path-on-row with a non-guessable name, so the route never builds a path from
   user input (path-traversal-safe by construction). Settle in implementation.

---

## How <!-- required -->

### Approach <!-- required -->

**Data model.** New SQLModel table `recordings`:

| column | type | notes |
|---|---|---|
| `id` | int PK | |
| `chunk_id` | int FK → `chunks.id`, **unique** | one recording per chunk; unique constraint enforces overwrite semantics |
| `file_path` | str | relative path under the recordings dir; non-guessable name |
| `content_type` | str | e.g. `audio/webm;codecs=opus` — echoed on playback |
| `size_bytes` | int | for the upload cap + diagnostics |
| `duration_seconds` | float \| None | optional; client-reported, best-effort |
| `created_at` | datetime | |

Alembic migration adds the table. `Chunk` gains a
`recording: Optional["Recording"] = Relationship(...)` back-reference;
`cascade` / explicit delete ensures `DELETE /api/chunks/{id}` removes the
recording row (and the route deletes the file).

**Storage.** A `recordings/` directory at repo root (sibling of `temp/`),
configurable via `config.py` (e.g. `RECORDINGS_DIR`), added to `.gitignore` and
`.dockerignore`. Unlike `temp/` (transient, cleaned per-flow), this directory is
durable. Files are written on upload and removed on overwrite/delete.

**Repository.** `RecordingRepository(session)` mirroring `ChunkRepository`'s
shape: `get_by_chunk_id`, `upsert(chunk_id, file_path, content_type, size,
duration)` (delete-old-file-then-write semantics live in the route/service, the
repo owns the row), `delete(chunk_id)`. `to_response(row)`.

**Routes** (extend `src/api/routes/chunks.py`, same router):

- `POST /api/chunks/{chunk_id}/recording` — `UploadFile` multipart. Validate
  chunk exists (404 else). Enforce size cap (413 else). Write file under
  `RECORDINGS_DIR`; if a prior recording exists, delete its file first. Upsert
  the row. Return `RecordingResponse` (201).
- `GET /api/chunks/{chunk_id}/recording` — look up row (404 else),
  `FileResponse` with `media_type=row.content_type`.
- `DELETE /api/chunks/{chunk_id}/recording` — delete row + file (404 if absent),
  204.
- Extend `ChunkResponse` with `has_recording: bool`. `ChunkRepository.list_all`
  already `selectinload(Chunk.video)`; add `selectinload(Chunk.recording)` so
  `to_response` reads the flag without an N+1.

**Schemas.** Add `RecordingResponse` (`id`, `chunk_id`, `content_type`,
`size_bytes`, `duration_seconds`, `created_at`) to `models/schemas.py`. Add
`has_recording` to `ChunkResponse`.

**Frontend cutover** (`webapp/`):

- Replace the `REC_STUB_MS` timer in `ChunkCard.tsx` with a real
  `useMediaRecorder`-style hook: `navigator.mediaDevices.getUserMedia({ audio:
  true })` → `MediaRecorder` → collect chunks → `Blob` on stop → `POST`
  multipart to `/api/chunks/{id}/recording`. Handle permission-denied / no-API
  with a Spanish inline message.
- Add playback: when `chunk.has_recording`, render an `<audio>` (or a play
  button that points at `GET /api/chunks/{id}/recording`) plus a delete control.
- API client (`webapp/src/lib/api.ts`): add `uploadRecording(id, blob)`,
  `deleteRecording(id)`, and a recording URL helper. Add `has_recording` to the
  `Chunk` type (`api-types.ts`).
- Invalidate `["chunks"]` after upload/delete so the card (and any other reader)
  reflects the new state — same single-source-of-truth pattern as 020.
- Client-side max-duration auto-stop (OQ2).

**Data flow.** Record (browser) → `POST` multipart → file written under
`RECORDINGS_DIR` + row upserted → `["chunks"]` invalidated → card shows playback
→ play hits `GET …/recording` streaming `FileResponse`. Delete chunk → cascade
removes recording row; route unlinks file.

### Confidence <!-- required -->

**Level:** Medium

**Rationale:** The backend half is high-confidence — it's a near-copy of 019's
repository/route/schema/migration shape, with the only new wrinkles being
multipart upload handling and on-disk file lifecycle (write/overwrite/delete +
orphan avoidance), both standard FastAPI. The uncertainty is the browser audio
round-trip: `MediaRecorder` output format varies by browser, and I want to
confirm that the bytes we store play back through a plain `<audio>` element with
the stored `content_type` and no transcoding. Permission/secure-context
handling (`getUserMedia` requires HTTPS or `localhost`) is a known constraint
but `localhost:3000` satisfies it.

**Validate before proceeding:** A thin end-to-end spike before wiring the full
card — in the browser, `getUserMedia` → record a few seconds → `POST` the blob
to a stub endpoint that writes the file → `GET` it back into an `<audio
src>` → confirm it plays. This validates (a) the captured MIME type, (b) that
stored-then-served bytes are playable as-is, and (c) the secure-context /
permission path on `localhost`. If playback fails as-stored, fall back to
constraining `MediaRecorder` to a known `mimeType` the `<audio>` element accepts.
Raises confidence Medium → High.

### Key Decisions <!-- optional -->

- **Filesystem + DB path over DB blob or object storage.** Chosen for a
  single-user single-process deploy: keeps the DB lean (audio bytes never travel
  through SQL), mirrors the existing `temp/` file pattern, and avoids adding an
  S3-class dependency the local stack doesn't have. Cost: the route owns file
  lifecycle (orphan-cleanup on overwrite/delete), and DB backup no longer
  captures the audio — acceptable at this scale. (DB blob was rejected for
  bloat + large-blob-over-SQL; object storage rejected as premature.)
- **One recording per chunk, overwrite (unique `chunk_id`).** Matches the single
  rec-button in the design; no history UI, no storage growth, no mastery signal
  to justify keeping takes. The unique constraint makes overwrite the only
  possible semantics — re-record deletes-then-writes.
- **`has_recording` on the list response, not a per-card fetch.** Avoids N
  round-trips when rendering N cards; `selectinload(Chunk.recording)` keeps it a
  single query, consistent with how 019 fixed the `video` N+1.
- **Store bytes as-received; no server-side transcoding.** The server is a dumb
  store; the recording browser and the playback browser are the same (single
  user), so the format it produced is a format it can consume.

### Testing Approach <!-- required -->

Per OVERVIEW's testing posture: **backend gets pytest coverage** (the suite from
025, now 102 tests, SQLite-backed with monkeypatched service singletons);
**frontend stays on manual smoke** (the 014–020 posture — `pnpm lint` +
`typecheck` + `build` green, plus a documented manual walkthrough against `make
dev` + seeded data, since `getUserMedia` can't run headless).

Backend test cases (new `tests/test_recording_routes.py`, reusing the
`seeded_video` + a saved chunk fixture from `conftest.py`):

- `POST` a small audio payload → 201, row created, file written, response shape
  correct.
- `POST` a second time to the same chunk → overwrites: old file gone, new file
  present, still exactly one row (unique constraint holds).
- `POST` to a non-existent `chunk_id` → 404, no file written.
- `POST` over the size cap → 413, no row, no file.
- `GET` after a `POST` → 200, bytes match what was uploaded, `Content-Type`
  matches the stored `content_type`.
- `GET` on a chunk with no recording → 404.
- `DELETE` → 204, row gone, file gone; second `DELETE` → 404.
- `GET /api/chunks` after a `POST` → the chunk's `has_recording` is `true`;
  before, `false`. (No N+1 — assert single query if the suite has a query-count
  harness; otherwise just correctness.)
- `DELETE /api/chunks/{id}` (the chunk itself) cascades: recording row gone, file
  unlinked — no orphan on disk.
- Path-traversal guard: a crafted `chunk_id` / filename can't escape
  `RECORDINGS_DIR` (the file path is derived server-side, never from user input —
  assert the stored path stays under the configured dir).

Tests write to a temp recordings dir (pytest `tmp_path`, `RECORDINGS_DIR`
overridden via the settings monkeypatch) so they never touch the real
`recordings/`.

Frontend manual smoke (documented for the PR walkthrough, run against `make dev`
+ a seeded chunk):

1. Grant mic permission; record on a chunk card; confirm live `is-recording`
   state.
2. Stop; confirm upload succeeds and a playback control appears.
3. Play; confirm own audio plays back.
4. Reload Mis frases; confirm the playback control persists.
5. Re-record; confirm it overwrites (one take, new audio).
6. Delete the recording; confirm the card returns to no-recording state.
7. Deny mic permission; confirm a clear Spanish message, no broken button.
8. Delete the chunk; confirm no orphaned file remains under `recordings/`.
</content>
</invoke>
