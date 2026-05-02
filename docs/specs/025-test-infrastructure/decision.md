# Decision: Test infrastructure + ruff bootstrap

| Field | Value |
|---|---|
| spec | [spec.md](./spec.md) |
| created | 2026-05-02 |
| status | implemented |

## Outcome

Spec landed as written. 17 tests across 4 files, ruff-clean, single GitHub Actions CI job. The SQLite primary path was viable; Postgres fallback was not triggered.

## DB choice — SQLite kept

The Alembic-against-`sqlite:///:memory:` spike (spec Confidence §2) hit one snag: migration `c6440d9b9453_change_h5p_content_type_to_json.py` used `op.alter_column(... type_=sa.JSON, postgresql_using=...)`, which SQLite doesn't support (no `ALTER COLUMN TYPE` at all).

Cost to fix was ~5 minutes — wrap the upgrade/downgrade bodies in a `bind.dialect.name == 'sqlite'` early-return guard. Rationale for the guard rather than a full batch_alter_table rewrite: the `h5p_content` column is dropped entirely two migrations later (`375de2969af7_remove_h5p_content`), so on SQLite the type change is a no-op for end state. The fix is in the migration file, not in test infra, and Postgres production behavior is unchanged.

The seven other migrations applied cleanly. SQLite path stays.

## ruff configuration deviations from defaults

Three per-file `E501` ignores in `[tool.ruff.lint.per-file-ignores]`:

- `src/services/questions.py` — long Spanish prompt strings sent to Claude. Wrapping them would rewrite the prompt the model sees.
- `src/services/dialect_classifier.py` — same reason.
- `src/repositories/classifier_repository.py` — same reason (duplicate dialect-classifier prompt; flagged separately in OVERVIEW audit notes for future consolidation).
- `alembic/versions/*.py` — auto-generated migration bodies; leave the original formatting intact for diff parity.

One `# noqa: F401` in `alembic/env.py` for `from models import database` — load-bearing import that registers SQLModel tables on `SQLModel.metadata` so `alembic revision --autogenerate` can diff against them. ruff F401 doesn't know it's load-bearing; the `# noqa` plus a one-line comment explains why.

## Spike outcomes

1. **Prefect import safety** — confirmed safe. Importing `api.routes.videos` (which imports `flows.video_processing` which imports `from prefect import flow, task`) does not hit a Prefect API server. The `@flow` decorator triggers runtime only on first *call*, which the route tests stub via `monkeypatch.setattr("api.routes.videos.process_video_flow", ...)`.

2. **Alembic against `:memory:`** — viable after the one-line `c6440d9b9453` guard described above. The `config.attributes["connection"]` pattern (small tweak in `alembic/env.py:run_migrations_online`) hands the existing engine's connection to Alembic so `:memory:` state is shared between fixture setup and migration application.

3. **`BackgroundTasks` ordering with TestClient** — confirmed. FastAPI's `TestClient` runs `BackgroundTasks` synchronously *after* the response is returned, so `client.post(...)` returns only after `run_flow_background` has finished. Tests assert the `COMPLETED` / `FAILED` row state immediately after the POST without any sleeps or polling.

## Existing-code cleanups that landed in this PR

Surfaced by ruff and confirmed in the OVERVIEW audit notes:

- `src/main.py` — duplicate `import os` removed (was line 1 + line 6 of the original).
- `src/db.py` — `create_db_and_tables` deleted. Zero callers; Alembic owns schema. Kept `engine`, `get_session`, `get_db_session`.
- 14 unused imports across `src/services/*` and `src/repositories/*` removed by `ruff check --fix`.
- 31 unsorted import blocks reordered by `ruff check --fix`.
- 1 bare `except:` → `except Exception:` in `src/services/questions.py:67` (intentional broad catch — kept the breadth, just made it ruff-acceptable).
- Format pass touched 32 files (whitespace, line breaks, quote consistency).

## What's verifiable now that wasn't before

- The `processing_jobs` schema (CHECK constraint, FK SET NULL, all 5 indexes) is asserted on every test run.
- The `/api/videos/status/{id}` response contract from PR #2 is locked: `youtube_video_id` + `video_id` present, `result` absent, `error` only on FAILED.
- The EXISTS short-circuit's "no row created" property is a test, not a manual verification step.
- Pagination on `/flows` is asserted, including newest-first order.
- The corrected `"Flow no encontrado"` 404 message is locked in.

## Known limitations carried forward

- **No CI Postgres job.** SQLite ignores some constraint enforcement (deferred FK, certain CHECK semantics). If we hit a Postgres-only bug, a follow-up roadmap item adds a second CI matrix entry — see spec §"Open Questions" §1 (deferred).
- **`spaCy es_dep_news_trf` is not exercised.** Tests for `FraseExerciseGeneratorService` are out of scope per the spec; loading the ~600 MB transformer in CI is its own infra problem.
- **Service-singleton mocking via monkeypatch, not DI.** Works; pragmatic. The DI refactor remains a candidate for its own spec.
- **`config.py` still raises at import.** Tests work around it via env stubs in `conftest.py`. The lazy-Settings refactor is its own work.
