# Spec: Test infrastructure + ruff bootstrap

| Field | Value |
|---|---|
| id | 025 |
| status | approved |
| created | 2026-05-02 |

---

## Why

The repo has zero tests today. PR #2 (012, flow-status persistence) shipped without a regression net because there was no test suite to add to, and the manual smoke test surfaced four distinct pre-existing bugs that no automated check would have caught (Prefect ephemeral migration, yt-dlp 403, partial-write inconsistency, missing spaCy model). Every future fix lands on the same shaky ground until this spec is implemented.

Item 025 was the only `planned` item the persistence fix surfaced as a hard prerequisite for further backend work. The frontend (013–016) is going to introduce a polling client against the `/status` and `/flows` endpoints whose contract just changed in PR #2 — without tests, the next change to that contract is a regression in production.

### Consumer Impact

- **Future Claude Code agents working in this repo.** Each `ss-fix` requires "tests written before fix"; without infra, that step is silently skipped and the codebase drifts. With this spec landed, every subsequent fix can produce a real failing test → passing test before/after artifact.
- **The human reviewer.** Manual curl smoke tests are the only verification today; they cost API credits and depend on a working YouTube + Anthropic + OpenAI + Prefect stack. A unit/integration suite removes that dependency for most checks.
- **Future CI.** Once the suite exists and runs in GitHub Actions, every PR gets free regression coverage on the parts of the system that don't need a real third-party API.

### Roadmap Fit

- **Unblocks:** 017 (Phrase Autopsy), 018 (token-level transcript), 019 (chunk library), 022 (user profile / KPIs) — all are non-trivial schema + endpoint additions where tests-as-you-go is the right cadence.
- **Doesn't block:** the frontend track (013–016, 020, 023) — that has its own testing story (component / E2E) which is out of scope here.
- **Bundled linter.** ROADMAP item 025 reads "Test suite + linter (none today)". Linter scope here is **ruff only** (lint + format in one tool — no black, no flake8, no isort). Default rule set, no project-specific overrides until a real friction surfaces.

---

## What

### Acceptance Criteria

- [ ] `uv run pytest` runs from a fresh checkout after `uv sync` and reports green.
- [ ] `uv run ruff check .` and `uv run ruff format --check .` both pass on the same checkout.
- [ ] DB fixture creates a fresh schema per test (or per session, fixture-scoped); the schema matches the live Alembic head — `processing_jobs`, `videos`, `questions`, `video_segments`, `answer_progress`, `frase_exercise` all present with the `ON DELETE SET NULL` FK and the `CHECK (status IN (...))` constraint on `processing_jobs`.
- [ ] At least one repository test for `ProcessingJobRepository` covering `create_pending → mark_running → mark_completed/mark_failed → get_by_flow_run_id → list`.
- [ ] At least one route test for `POST /api/videos/process-async`, `GET /api/videos/status/{id}`, and `GET /api/videos/flows` exercising the persistence layer end-to-end with `process_video_flow` mocked.
- [ ] All external services (Anthropic, OpenAI, yt-dlp, YouTube Data API, Prefect ephemeral API) are mocked or unreachable during tests — no live API call ever happens in `pytest`.
- [ ] The eager API-key validation in `src/config.py` does not block test imports.
- [ ] A GitHub Actions workflow (`.github/workflows/ci.yml`) runs `ruff check`, `ruff format --check`, and `pytest` on every PR. It is green on this PR.
- [ ] After implementation: a short `docs/specs/025-test-infrastructure/decision.md` records the actual DB choice (SQLite vs Postgres, see Approach §1) and any ruff rule deviations from defaults.

### Non-Goals

- **Black / flake8 / isort / mypy.** Ruff covers lint + format; no second linter. Type checking is a separate decision.
- **Custom ruff rule set.** Default `[tool.ruff]` config. Add rules only when something concrete pushes back.
- **Auto-fix or pre-commit hooks.** CI checks; the human / agent runs `ruff format` before committing. Pre-commit framework can land later.
- **Coverage gates.** No `--cov-fail-under` enforcement. Run coverage advisory if it falls out cheap, but don't block PRs on it.
- **Spec coverage of the spaCy fill-in-blank generator (`FraseExerciseGeneratorService`).** Loading `es_dep_news_trf` (~600 MB transformer) inside CI is its own infra problem; tests for that service are deferred to a future spec or are written against a small mocked spaCy doc.
- **End-to-end flow tests.** No test will run the actual `process_video_flow` body; route tests stub it. A future spec can add testcontainer-backed integration tests for the full pipeline.
- **Property-based or fuzz testing.** Plain pytest only.
- **Async test plumbing for sync code.** FastAPI's `TestClient` is `requests`-based and sync; that's the default. `pytest-asyncio` is added only if a future test genuinely needs it.
- **Frontend tests.** This spec is backend-only.
- **Docker for local dev.** A Postgres testcontainer path is sketched as an optional CI addition (see Approach §4) but is not required to ship 025.

### Open Questions

1. **Mocking strategy for service singletons.** `question_service`, `dialect_classifier`, `transcription_service`, `youtube_search`, `youtube_service` are all module-level singletons that instantiate clients at import. Cleanest fix is dependency injection. Pragmatic fix is `monkeypatch.setattr` on the singleton's client attribute. Recommendation: monkeypatch for this spec; a refactor to DI is deferred.
2. **Should this PR include a sample test for one of the existing modules** (e.g., `VideoRepository`) **alongside the `ProcessingJobRepository` test?** Recommendation: yes — one repository test plus one route test is the smallest demonstration that the infra works.
3. **Existing code that fails ruff defaults.** The audit flagged things ruff would catch (`os` imported twice in `main.py`, dead `from db.py:create_db_and_tables`, etc.). Plan: fix what comes up in the same PR and call it out; if any rule produces noise that's clearly not worth fixing, disable it locally with a one-line `# noqa` and note the rule in the decision record.

---

## How

### Approach

Four layers, smallest to largest:

#### 1. Test database — try SQLite, fall back to Postgres

**Primary plan: in-memory SQLite via Alembic.** Fixture creates `sqlite:///:memory:`, enables `PRAGMA foreign_keys = ON` via `event.listens_for(engine, "connect")`, and applies the schema by running the actual Alembic migrations (not `SQLModel.metadata.create_all`) so we catch schema drift — the `CHECK` constraint and `ON DELETE SET NULL` live only in the migration body.

```python
@pytest.fixture
def engine():
    url = "sqlite:///:memory:"
    eng = create_engine(url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    @event.listens_for(eng, "connect")
    def _fk_pragma(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys = ON")
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    with eng.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")
    yield eng
```

`alembic/env.py` needs a one-line tweak to use `config.attributes["connection"]` when present (standard Alembic pattern).

**Fallback gate.** If the SQLite spike (see Confidence §validation) reveals genuine friction — Alembic migration that uses Postgres-only DDL, an unsupported constraint, FK enforcement that requires more than `PRAGMA`, or anything that costs more than ~1 hour to work around — switch to **Postgres via a GitHub Actions `services:` container locally and in CI**. Local devs run `docker run --rm -d -p 5433:5432 -e POSTGRES_PASSWORD=test postgres:16` and set `TEST_DATABASE_URL`. The fixture then uses an Alembic `upgrade head` against a per-test schema (`CREATE SCHEMA test_<uuid>; SET search_path TO ...`) for isolation, or just `DROP TABLE` between sessions.

The decision (which path landed) goes in `decision.md` after implementation — not in this spec.

#### 2. Session injection

`db.get_session` is the FastAPI dependency. The route tests use `app.dependency_overrides[get_session] = lambda: session` to bind handlers to the test session. Background tasks use `db.get_db_session` (context manager) — for route tests we monkeypatch `get_db_session` to yield the same test session, so the `mark_running` / `mark_completed` writes from `run_flow_background` land in the same in-memory DB the test will assert against.

#### 3. External-service mocking

| Boundary | How |
|---|---|
| Anthropic Claude (`question_service`, `dialect_classifier`, `ClassifierRepository`) | `monkeypatch.setattr` on the singleton's `.client` attribute with a stub that returns a `Message`-shaped object. Helper in `tests/_fakes.py`. |
| OpenAI Whisper (`transcription_service`) | Same pattern — stub `.client.audio.transcriptions.create` to return a deterministic `DetailedTranscript`. |
| yt-dlp (`youtube_service.download_audio`) | `monkeypatch.setattr(youtube_service, "download_audio", lambda url: ("/tmp/fake.mp3", {...}))`. |
| YouTube Data API (`youtube_search.search_videos`) | Same — return canned list. |
| `youtube_transcript_api.YouTubeTranscriptApi` | Patch at module level. |
| `process_video_flow` | For route tests, `monkeypatch.setattr("api.routes.videos.process_video_flow", stub)` where the stub returns a deterministic dict matching the live shape (`{"id": ..., "video_id": ..., ...}`) or raises a sentinel exception for failure-path tests. **No real Prefect runtime touched.** |

#### 4. Eager-import problem

`src/config.py:18-23` raises at import if `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or `YOUTUBE_API_KEY` are missing. `tests/conftest.py` sets stub values *before* any project module is imported, using a top-of-file block:

```python
import os
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic")
os.environ.setdefault("OPENAI_API_KEY", "test-openai")
os.environ.setdefault("YOUTUBE_API_KEY", "test-youtube")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
```

This is a workaround. The proper fix is to make `Settings` lazy (already noted in the audit). That refactor is out of scope here — it touches every module that imports `settings`, and the env-var stub is enough to unblock 025.

#### 5. Initial test set

| File | What it covers |
|---|---|
| `tests/test_processing_job_repository.py` | `create_pending`, transitions, `get_by_flow_run_id`, `list` ordering, `_set_status` no-op when row missing. Asserts `updated_at >= created_at`. |
| `tests/test_video_repository.py` | One test (smoke) — `create` + `get_by_youtube_id` round-trip. Demonstrates the infra works for an existing repository. |
| `tests/test_videos_routes.py` | `POST /process-async` happy path (mocked flow returns a video dict; assert PENDING row created, then COMPLETED after the BackgroundTask runs); `POST /process-async` failure path (mocked flow raises; assert FAILED with `error` set); `GET /status/{id}` 404 on unknown id; `GET /status/{id}` correct shape on COMPLETED (includes `youtube_video_id`, `video_id`, no `result`); `GET /flows` pagination defaults; EXISTS short-circuit (existing video → no `processing_jobs` row created). |

This is the minimum: ~10 tests across 3 files. Future items add their own.

#### 6. Project layout

```
tests/
  __init__.py
  conftest.py                       # env stubs, engine, session, app, client fixtures
  _fakes.py                         # stub Anthropic / OpenAI / yt-dlp objects
  test_processing_job_repository.py
  test_video_repository.py
  test_videos_routes.py
```

`pyproject.toml` gains a `[tool.pytest.ini_options]` block with `testpaths = ["tests"]`, `addopts = "-q"`, `pythonpath = ["src"]` (mirrors `alembic.ini`'s `prepend_sys_path = .` so `from db import …` keeps working in tests).

Dev dependencies via `[dependency-groups] dev = [...]` (uv convention): `pytest>=8.0`, `ruff>=0.7`. Plain `httpx` already comes via `fastapi[standard]`, so `TestClient` works without adding a dep. Stdlib `unittest.mock` plus pytest's `monkeypatch` covers our mocking needs.

#### 7. Ruff

Single dev dependency. Configuration lives in `pyproject.toml`:

```toml
[tool.ruff]
target-version = "py312"
src = ["src", "tests"]
line-length = 100  # generous; can tighten later

[tool.ruff.lint]
# Default rules: E (pycodestyle errors), F (pyflakes), I (isort).
# Add explicit selects only when defaults fall short.
select = ["E", "F", "I"]
```

Existing-code cleanups likely to surface and worth fixing in the same PR:
- `src/main.py:1,6` — `os` imported twice.
- `src/db.py:create_db_and_tables` — unused; delete if confirmed.
- Any unused imports flagged by `F401` across services.

If any default rule produces noise that's clearly busy-work (long error messages in question prompts, intentional dual statements), disable it inline with `# noqa: <RULE>` and note in `decision.md`.

#### 8. CI

`.github/workflows/ci.yml`:

```yaml
name: ci
on: [push, pull_request]
jobs:
  ci:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with: { python-version: "3.12" }
      - run: uv sync --frozen
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run pytest
```

If §1 ends up on the Postgres fallback, this becomes:

```yaml
    services:
      postgres:
        image: postgres:16
        env: { POSTGRES_PASSWORD: test, POSTGRES_DB: test }
        ports: ["5432:5432"]
        options: >-
          --health-cmd pg_isready --health-interval 5s --health-timeout 3s --health-retries 5
    env:
      TEST_DATABASE_URL: postgresql://postgres:test@localhost:5432/test
```

That's the entire CI commitment.

### Confidence

**Level:** Medium

**Rationale:**

- **High** on the SQLite + repository test path. SQLModel and SQLAlchemy support SQLite cleanly; the only known gotcha is `PRAGMA foreign_keys = ON`, which is a one-liner.
- **High** on the mocking strategy. Service singletons all expose their underlying client as a settable attribute; monkeypatching is well-trodden.
- **Medium** on running Alembic against `:memory:` in a fixture. The Alembic-uses-existing-connection pattern works but requires a one-line tweak in `alembic/env.py`. If that turns out brittle, the fallback is `SQLModel.metadata.create_all` plus a single migration-applies test — that path is rock-solid.
- **Medium** on whether `process_video_flow` is fully mockable without Prefect runtime side effects. The module imports `from prefect import flow, task`; just importing `api.routes.videos` (which imports `flows.video_processing`) might trigger Prefect init the same way the live server did. Validation needed before committing — see below.

**Validate before proceeding:**

1. **Spike: import the routes module with a fresh `PREFECT_API_URL` setting and confirm no side effects.** If Prefect's ephemeral API tries to start at import time, we either set `PREFECT_API_URL` to a non-existent stub in conftest before imports, or refactor the flow import out of the routes module. ~15 min.
2. **Spike: run Alembic against `sqlite:///:memory:` with the `attributes["connection"]` pattern.** If our existing migrations apply cleanly, ship as planned. **If any cost more than ~1 hour to make SQLite-compatible, abandon SQLite and switch to the Postgres `services:` fallback** (Approach §1). The user has explicitly signed off on this trade. ~30 min for the spike itself.
3. **Spike: confirm that overriding `get_db_session` (the context manager used inside `BackgroundTasks`) is reachable from a route test.** The dependency-override mechanism only covers `Depends()`-injected funcs; for the context manager, monkeypatch is the lever. Confirm the FastAPI `TestClient` runs `BackgroundTasks` synchronously after the response (it does, per FastAPI docs), so the assertion order in the test is deterministic. ~15 min.

Total spike budget: ~1 hour before committing the full implementation. If §2 hits the abandon-threshold, switch the DB choice and continue without re-specifying.

### Key Decisions

- **Try SQLite first, fall back to Postgres if SQLite costs more than ~1 hour to make work.** User has explicitly signed off on the fallback. The DB that actually ships goes in `decision.md`.
- **Run Alembic migrations in the fixture, not `metadata.create_all`.** Catches schema drift, e.g. the CHECK constraint that lives only in the migration body.
- **Monkeypatch service singletons rather than refactor to DI.** Smallest change for biggest verification. The DI refactor is its own decision when it's worth doing.
- **Stub env vars in `conftest.py` rather than make `Settings` lazy.** Lazy `Settings` is a real refactor and lands later. Stubs unblock now.
- **Ruff only, default rules.** No black, no flake8, no isort, no mypy. Add rules only when something concrete pushes back.
- **One CI job, not a matrix.** If we ship SQLite, no Postgres job; if we ship Postgres, no SQLite job. Matrix testing is overkill for a single-deployment app.

### Testing Approach

This spec *is* the testing approach. The "tests for this spec" are the tests it ships:

- **Repository layer:** unit tests against the in-memory engine. Fast (<1s combined).
- **Route layer:** integration tests via `fastapi.testclient.TestClient` with `app.dependency_overrides[get_session]` and `monkeypatch` on `process_video_flow` and the service singletons. Each test creates a fresh DB.
- **Migrations:** validated transitively by every test that uses the `engine` fixture (since the fixture runs `alembic upgrade head`).

Acceptance is mechanical: `uv run pytest` exits 0 with at least 8 passing tests, and the GitHub Actions job is green.
