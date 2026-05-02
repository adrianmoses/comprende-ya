# 012 — Flow-status persistence

| Field | Value |
|---|---|
| status | approved |
| created | 2026-05-02 |
| roadmap | [012](../ROADMAP.md) |
| author | inferred from audit |

## Problem

`src/api/routes/videos.py:29` declares a module-level `flow_runs = {}` dict that holds the lifecycle of every async video-processing job (`PENDING → RUNNING → COMPLETED/FAILED`, plus the URL and a result payload on success). The flow itself runs end-to-end and persists video data to PostgreSQL correctly; only the *status surface* exposed by `GET /api/videos/status/{flow_run_id}` and `GET /api/videos/flows` is broken.

The dict has three failure modes:

1. **Volatile.** A server restart drops every entry. The flow continues to run if the worker is preserved (it isn't, since the flow runs as a FastAPI `BackgroundTask` in the same process), or, more commonly, the work is gone and the polling endpoint returns 404 forever even after the underlying `Video` row eventually appears.
2. **Unbounded.** Every processed video accumulates an entry — including the full `result` payload (`videos.py:42-46`) — for the lifetime of the process. No TTL, no cap.
3. **Process-local.** A multi-worker deploy (`gunicorn -w 2`, future Kubernetes replicas) gives each worker its own dict. Polling round-robins between them and the frontend gets random 404s. This is the hidden constraint that quietly forces single-worker uvicorn today.

The frontend in `docs/artefacts/` is built around a poll-until-COMPLETED loop. Landing it against the dict would couple the planned UI to volatile state.

## Solution

Replace the dict with a `processing_jobs` Postgres table. The `BackgroundTasks` orchestration stays as-is — durable resume across restarts is a separate, larger problem (see Out of Scope).

### Schema

```sql
CREATE TABLE processing_jobs (
    id                 SERIAL PRIMARY KEY,
    flow_run_id        VARCHAR(36)  NOT NULL UNIQUE,
    youtube_url        VARCHAR      NOT NULL,
    youtube_video_id   VARCHAR(32)  NOT NULL,
    status             VARCHAR(16)  NOT NULL DEFAULT 'PENDING',
    error              TEXT         NULL,
    video_id           INTEGER      NULL REFERENCES videos(id) ON DELETE SET NULL,
    created_at         TIMESTAMP    NOT NULL,
    updated_at         TIMESTAMP    NOT NULL,
    CONSTRAINT ck_processing_jobs_status
        CHECK (status IN ('PENDING','RUNNING','COMPLETED','FAILED'))
);
CREATE UNIQUE INDEX ix_processing_jobs_flow_run_id      ON processing_jobs(flow_run_id);
CREATE        INDEX ix_processing_jobs_youtube_video_id ON processing_jobs(youtube_video_id);
CREATE        INDEX ix_processing_jobs_status           ON processing_jobs(status);
CREATE        INDEX ix_processing_jobs_created_at       ON processing_jobs(created_at);
CREATE        INDEX ix_processing_jobs_video_id         ON processing_jobs(video_id);
```

Column rationale:

- **`id` (integer PK)** — internal surrogate, matches every other table in this repo (`videos`, `questions`, `answer_progress`, `frase_exercise`).
- **`flow_run_id` (uuid hex string)** — public identifier; today's caller already does `str(uuid.uuid4())`. Unique-indexed but not the PK so internal/external identity stay separable, mirroring `videos.youtube_id` vs `videos.id`.
- **`youtube_url`** — needed for `GET /flows` listing (today's response includes `url`).
- **`youtube_video_id`** — extracted via regex *before* the job is created (`videos.py:114-118`), so always known at insert. Non-unique because forced reprocessing creates a second row for the same video.
- **`status` (`VARCHAR(16) + CHECK`)** — string + CHECK constraint, not `sa.Enum`. Postgres `ENUM` types are painful to alter later; the existing schema uses no enums anywhere.
- **`error` (`TEXT`)** — `str(e)` from `process_video_flow` can include long stack traces.
- **`video_id` (FK, `ON DELETE SET NULL`)** — populated when the flow lands a `Video` row (we already have `result["id"]`). `SET NULL` not `CASCADE`: deleting a video shouldn't erase its job audit row.
- **`created_at` indexed** — `GET /flows` sorts newest-first.

### Endpoint contract

`POST /api/videos/process-async` — unchanged shape. Replaces the dict write with `ProcessingJobRepository(db).create_pending(...)`. EXISTS short-circuit (cache hit, `force=false`, video already in DB) is deliberately unchanged: still returns `{flow_run_id: None, status: "EXISTS", result: {...}}` and creates no `processing_jobs` row. EXISTS is not a flow run — synthesizing a `COMPLETED` row on every refresh would inflate the listing endpoint.

`GET /api/videos/status/{flow_run_id}` — response shape **changes**:

```diff
 {
   "flow_run_id": "...",
   "status": "COMPLETED",
-  "url": "https://youtube.com/...",
-  "result": { "id": 17, "video_id": "dQw4w...", "title": "...",
-              "transcript": "...", "questions": [...], "exercise_count": 12 }
+  "url": "https://youtube.com/...",
+  "youtube_video_id": "dQw4w9WgXcQ",
+  "video_id": 17
 }
```

The `result` payload is dropped. Frontend fetches `GET /api/videos/{youtube_video_id}` once it sees `status === "COMPLETED"`. Rationale: avoids re-serializing the video on every poll (a 2 Hz polling client would otherwise pay video+questions+exercises queries 150 times for one 5-minute job), and keeps the `videos` table as the single source of truth for processed-video data. `error` is included only when status is `FAILED`. The 404 typo (`"Flow encontrado"`) is fixed in the same edit.

`GET /api/videos/flows` — adds optional `skip` (default 0) and `limit` (default 50, max 200) query params and reads from the repo. Per-row shape is unchanged (`{flow_run_id, status, url}`); the `{"flows": [...]}` wrapper is unchanged. Backwards-compatible for callers that omit the params.

### Implementation surface

| File | Change |
|---|---|
| `src/models/database.py` | + `ProcessingJob` SQLModel |
| `src/repositories/processing_job_repository.py` | new file (sync, `Session`-injected, mirrors `ProgressRepository`) |
| `src/repositories/__init__.py` | re-export `ProcessingJobRepository` |
| `alembic/versions/<gen>_add_processing_jobs_table.py` | new migration, `down_revision="cd3ded574f5e"` |
| `src/api/routes/videos.py` | delete `flow_runs`; rewrite `run_flow_background`, `process_video_async` write, `get_flow_status`, `get_flows`; fix 404 typo |

`run_flow_background` keeps its `(flow_run_id, video_url, force=False)` signature so the `BackgroundTasks.add_task(...)` site is unchanged. Internally each transition opens a short-lived session via the existing `db.get_db_session()` context manager — the same one `flows/video_processing.py:48,105,116,126` already uses from background tasks. Holding a session across the multi-minute flow would tie up a connection from the pool for no benefit.

## Verification

This PR ships **without automated tests** — the repo currently has none, and bootstrapping pytest is its own decision (see ROADMAP item 025). Manual `curl` checklist:

1. `alembic upgrade head` — table, indexes, and CHECK constraint exist (`\d processing_jobs` in psql).
2. `POST /api/videos/process-async` with a fresh URL → `{flow_run_id, status: "PENDING"}`. Confirm a row exists with `status='PENDING'` and `youtube_video_id` populated.
3. Within ~1s, `GET /api/videos/status/{flow_run_id}` returns `status='RUNNING'`.
4. After flow completes (~minutes), status → `COMPLETED`, `video_id` populated, FK points at the new `videos` row. Response has no `result` field.
5. Trigger failure (e.g., a bad URL the regex passes but yt-dlp rejects) → status → `FAILED`, `error` populated.
6. Restart the FastAPI process mid-flow → row stays `RUNNING` in DB; polling endpoint resolves (no 404). See Known Limitations.
7. `GET /api/videos/flows?skip=0&limit=10` paginates, newest-first.
8. EXISTS: re-POST the same URL with `force=false` → `flow_run_id: None`, no new row.
9. `alembic downgrade -1 && alembic upgrade head` — round-trip clean.

## Known Limitations

- **Stale `RUNNING` rows after restart.** The flow runs in the FastAPI process via `BackgroundTasks`; killing the process leaves the row at `RUNNING` forever (no resume, no auto-FAIL). Documented and accepted for this fix; durable resume requires a real Prefect deployment.
- **No row eviction.** Completed and failed jobs accumulate indefinitely. Listing pagination keeps the endpoint usable; a TTL/sweep is a future spec.
- **Single-process orchestration.** Multiple FastAPI workers running the same `process_video_flow` for the same URL would still race to insert two `processing_jobs` rows (and the `youtube_id` uniqueness constraint on `videos` would surface the conflict at save time). Fine for current single-worker deploy.

## Out of Scope

- TTL / eviction
- Retry endpoint (`POST /retry/{flow_run_id}`)
- Stuck-job detection / startup auto-FAIL
- Multi-worker / multi-replica coordination
- Replacing `BackgroundTasks` with a real Prefect deployment / worker pool
- Job cancellation
- Test suite bootstrap (covered by ROADMAP item 025)
