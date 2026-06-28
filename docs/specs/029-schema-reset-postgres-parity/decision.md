# Decision Record: Schema reset — models authoritative + Postgres test parity

| Field | Value |
|---|---|
| id | 029 |
| status | implemented |
| created | 2026-06-28 |
| spec | [spec.md](./spec.md) |

---

## Context

`alembic revision --autogenerate` had become untrustworthy: every run re-proposed
unrelated FK/index/constraint churn because the SQLModel classes under-declared
what the migrations built, and the SQLite-tests / Postgres-prod split layered
dialect noise on top. It had already forced hand-stripping twice during the 021
work. With the project local-only on throwaway data, the spec chose a **full
reset** over a reconciling patch: make the models authoritative, squash to one
Postgres-native baseline, and move the test suite onto Postgres.

Two things shaped the implementation beyond the spec:

1. **No Docker in the working environment.** The spec leaned testcontainers for the
   test Postgres; the dev machine has a *native* Postgres (the Procfile has no
   Postgres line) and no Docker daemon. So the `DATABASE_URL_TEST` fallback became
   the primary path — simpler, and CI uses a services-postgres anyway.
2. **A migration-only CHECK constraint the spec didn't name.** `processing_jobs`
   carries `CHECK (status IN ('PENDING','RUNNING','COMPLETED','FAILED'))`
   (`ck_processing_jobs_status`), present only in the migration body and guarded by
   `test_db_fixture.py`. A naive squash-from-models would have silently dropped it.

## Decision

The SQLModel classes now declare their full schema intent — FK `ondelete`
(`answer_progress`/`frase_exercise`/`processing_jobs`/`recordings`), the
`unique_video_question_progress` constraint, the `ck_processing_jobs_status` CHECK,
and `processing_jobs.error` as `TEXT` — via `sa_column=Column(...)` and
`__table_args__`. The 11 historical migrations were deleted and replaced by a
**single Postgres-native baseline** (`1b329637734b`, `down_revision=None`)
regenerated from the corrected models. The test suite runs against a real Postgres
via `DATABASE_URL_TEST` (default local `comprende_ya_test`), with a session-scoped
baseline schema and per-test `TRUNCATE … RESTART IDENTITY CASCADE` isolation. CI
provisions a `postgres:16` service.

The definitive success test passes: on a fresh Postgres, `alembic upgrade head`
followed by `alembic revision --autogenerate` produces a migration with **zero
operations**. No product behavior or data changed; `pyproject.toml`/`uv.lock` are
unchanged from main (net-zero dependency change).

---

## Alternatives Considered

### Killing the drift — squash vs patch vs suppress

**Option A — Reconciling patch migration.** Add one corrective migration on top of
the existing 11.
- Pros: preserves history.
- Cons: history has no value here (no deployment pinned to the hashes); stacks a
  patch on accreted drift; the SQLite compat hacks survive.

**Option B — Squash to one baseline (chosen).**
- Pros: collapses 11 migrations + the drift into one honest baseline; autogenerate
  clean by construction; no compat hacks.
- Cons: rewrites history — safe only because the project is local-only.

**Option C — Suppress via `include_object`/`compare_type` hooks in `env.py`.**
- Cons: models keep lying about the schema; the hooks are a maintenance trap.

**Chosen:** B. The user explicitly authorized a schema restart; with no data to
preserve, a single baseline is strictly cleaner than patching.

### Test Postgres provisioning — testcontainers vs DATABASE_URL_TEST

**Option A — testcontainers (the spec's lean).** Spin a container per session.
- Pros: self-contained; same path local + CI.
- Cons: **requires Docker, which the dev environment doesn't have**; adds a heavy
  dependency.

**Option B — `DATABASE_URL_TEST` against a plain Postgres (chosen).**
- Pros: zero new dependency; uses the native local Postgres the developer already
  runs, and a GitHub Actions services-postgres in CI; both just a connection URL.
- Cons: the test DB must exist (a one-line `createdb` locally; declared in CI).

**Chosen:** B, a deviation from the spec's lean, forced by the no-Docker reality and
better regardless (no net dependency). The spec's OQ1 explicitly allowed
`DATABASE_URL_TEST` as the override, so this stays within the approved envelope.

### Test isolation — transactional rollback vs truncate

**Option A — Session joined to an external transaction, rolled back per test.**
- Cons: the repositories call `session.commit()`, so a rollback wouldn't undo their
  writes without the fiddly savepoint-restart recipe.

**Option B — `TRUNCATE … RESTART IDENTITY CASCADE` after each test (chosen).**
- Pros: robust against committing repos; resets sequences for determinism; simple.
- Cons: slightly slower than rollback (negligible — full suite ~11s).

**Chosen:** B. An autouse function-scoped fixture so it also cleans the
`engine`-based raw-SQL tests in `test_db_fixture.py`, not just `session` consumers.

---

## Tradeoffs

- **Postgres test parity over the fast in-memory SQLite suite.** Tests now exercise
  the production engine — real CHECK/FK enforcement, real types — at the cost of
  requiring a Postgres (native locally, service in CI) instead of zero-dependency
  SQLite. Suite time went from ~8s to ~11s. The dialect-drift class is gone.
- **Squash erases migration history.** Acceptable only because nothing is deployed;
  recorded as a key constraint so it isn't repeated once the project ships.
- **Models carry `sa_column` verbosity.** FK `ondelete` and CHECK declarations make
  the model classes wordier than bare `Field(foreign_key=...)`, but that verbosity
  *is* the fix — the declarations are now the single source of truth.
- **Test DB lifecycle is the developer's.** `DATABASE_URL_TEST` assumes the test
  database exists; documented, and CI creates it via the service. A missing local
  `comprende_ya_test` is a one-line `createdb`.

---

### Spec Divergence

| Spec Said | What Was Built | Reason |
|---|---|---|
| Provision test Postgres via **testcontainers** (OQ1 lean), `DATABASE_URL_TEST` as fallback | `DATABASE_URL_TEST` is the **only** mechanism; testcontainers not used | No Docker in the dev environment; CI uses services-postgres. Net-zero dependency, simpler. Within OQ1's allowed envelope. |
| Declare FK ondelete, unique constraint, indexes, `error` TEXT | All of those **plus** the `ck_processing_jobs_status` CHECK | The CHECK was migration-only and guarded by `test_db_fixture.py`; the squash would have dropped it. Not a divergence so much as a gap the spec missed (see below). |
| Isolation: session schema + transactional rollback (OQ2 lean) | session schema + **TRUNCATE** isolation | Repos commit, so rollback wouldn't undo writes; truncate is robust. OQ2 anticipated this. |

All acceptance criteria met. The empty-diff criterion — the headline — passes.

---

## Spec Gaps Exposed

1. **The `processing_jobs.status` CHECK constraint was not in the spec's enumeration
   of drift.** It lived only in the migration body and would have been silently lost
   in a squash-from-models. Caught because `test_db_fixture.py` guards it. Lesson:
   before squashing, audit migrations for constraints models don't declare (CHECK,
   server defaults, partial indexes) — autogenerate does **not** compare CHECK
   constraints, so it won't warn you either way.

2. **The spaCy model + `torch` live outside `uv.lock`** (manual `spacy download` per
   CLAUDE.md), so every `uv sync` / `uv run` prunes them. This bit the work twice
   (a stray `uv add`/`uv remove` and the `uv sync --frozen` CI-gate check both
   removed the model). Tests are unaffected (they mock `get_nlp`), so CI is green —
   but the real video-processing flow breaks locally after any `uv` sync. Tracked as
   new roadmap item **030**.

3. **`DATABASE_URL_TEST` assumes the test DB exists.** Not a code gap, but worth a
   one-line note in the developer setup (a `createdb comprende_ya_test` step) since
   the conftest no longer self-provisions (no testcontainers).

---

## Test Evidence

Headline — empty autogenerate diff against a fresh Postgres at `head`:

```
$ alembic upgrade head        # -> 1b329637734b, baseline schema
$ alembic revision --autogenerate -m _check
# generated migration body:  def upgrade(): pass   (op.* count: 0)
```

Full suite on real Postgres — no regression, no behavioral edits:

```
$ uv run pytest
114 passed in 10.83s
```

Lint/format clean; dependency files unchanged from main:

```
$ uv run ruff check .          → All checks passed!
$ uv run ruff format --check . → 54 files already formatted
$ git diff --stat main -- pyproject.toml uv.lock   → (no changes)
```

Single baseline migration present (11 prior migrations deleted):

```
$ ls alembic/versions/*.py
alembic/versions/1b329637734b_baseline_schema.py
```

`test_db_fixture.py` now validates the CHECK constraint and FK `ON DELETE SET NULL`
against real Postgres (previously SQLite-PRAGMA-dependent). CI provisions a
`postgres:16` service with `DATABASE_URL_TEST`.
</content>
