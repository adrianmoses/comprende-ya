# Decision Record: Deployment Readiness — externalize config + ship both services

| Field | Value |
|---|---|
| id | 033 |
| status | implemented |
| created | 2026-06-29 |
| spec | [spec.md](./spec.md) |

---

## Context

033 closed five deploy blockers and folded in item **030** (managed model deps).
The spec target was a self-host Docker Compose stack (api + webapp + postgres),
verified by a local prod-mode smoke — no live cloud deploy.

Two facts only surfaced once the work was actually exercised, and both changed
the approach the plan had written down:

1. **The model's transformer backend.** `es_dep_news_trf` 3.8.0's `meta.json`
   requires `spacy-curated-transformers` (>=0.2.2,<1.0.0) — **not**
   `spacy-transformers`, which the plan named. The plan's dep was wrong;
   inspecting the installed model's requirements caught it before it shipped.
2. **TanStack Start no longer emits a Nitro node-server.** The spec and
   ARCHITECTURE.md describe a "Nitro node-server" you run with
   `node dist/server/server.js`. In the pinned version (`@tanstack/react-start`
   1.167.61) `vite build` emits a **web-fetch handler** (`export default { fetch }`),
   not a self-listening HTTP server. Running the bundle directly bound nothing.

A third, quieter constraint: this dev box is macOS **x86_64**, and `torch` dropped
macOS-x86_64 wheels after 2.2.2 — so the lockfile had to keep torch resolvable on
both that platform and linux/amd64.

The Docker daemon was down at implementation start; the operator started it on
request and the full smoke ran to completion.

## Decision

Ship a self-host `docker-compose.yml` (db + api + webapp). The API image now
installs `torch` (CPU) + `spacy-curated-transformers` + the `es_dep_news_trf`
wheel as **uv-tracked, lockfile-pinned** dependencies, so `uv sync --frozen`
alone produces an image whose exercise generation works — no `spacy download`
step. A `docker-entrypoint.sh` runs `alembic upgrade head` then `exec`s the
server (migrate-then-serve, idempotent). CORS reads `ALLOWED_ORIGINS` from the
environment (localhost dev default when unset). `recordings/` is a named volume.
The webapp ships its own image that builds the TanStack Start bundle and serves
the emitted fetch handler over Node via **srvx** (`webapp/server.mjs`), with
`VITE_API_BASE_URL` injected as a build arg. The public-origin contract
(`PUBLIC_API_URL` / `ALLOWED_ORIGINS` = browser-reachable, never `http://api:8000`)
is documented in `.env.example` and the README.

---

## Alternatives Considered

### Production-serve mechanism for the webapp

**Option A — `node dist/server/server.js` (as the spec/plan assumed).**
- Pros: zero new deps, matches the "Nitro node-server" mental model.
- Cons: **doesn't work** — the bundle is a fetch handler with no listener;
  running it binds no port.

**Option B — hand-rolled `node:http` → Web `fetch` bridge.**
- Pros: no new dependency.
- Cons: must correctly bridge streaming bodies, headers, and `Request`/`Response`
  semantics by hand; fragile and easy to get subtly wrong for SSR streaming.

**Option C — feed the handler to `srvx` (chosen).**
- Pros: `srvx` is TanStack Start's *own* server runtime (already present in the
  tree as a transitive dep); a 6-line adapter; honors `PORT`/`HOST`; correct
  streaming. Promoting it to a direct dep pins it at the in-tree version.
- Cons: one explicit dependency the framework normally hides.

**Chosen:** C. The adapter (`webapp/server.mjs`) imports the built handler's
`default.fetch` and serves it; verified to return the real SSR app (HTTP 200,
`<title>Comprende Ya</title>`, themed shell).

### Installing the spaCy model in the image (the 030 fix)

**Option A — explicit `python -m spacy download es_dep_news_trf` in the Dockerfile.**
- Pros: simple, obvious.
- Cons: not lockfile-tracked → leaves 030's root cause (uv prunes it) open for
  local dev; an out-of-band network step at build time.

**Option B — uv-tracked wheel dependency (chosen).**
- Pros: `es-dep-news-trf` becomes a real entry in `pyproject.toml`
  `[tool.uv.sources]` + `uv.lock` (with sha256); `uv sync --frozen` reproduces it
  everywhere — solves 030 at the repo level, not just in the image.
- Cons: pins the model URL/version explicitly; bumping spaCy means bumping the
  wheel URL too.

**Chosen:** B — it's the spec's preferred path and actually closes 030.

### torch version constraint

**Option A — unpinned `torch`.** Risked the lock picking a version with no
macOS-x86_64 wheel, breaking `uv sync` on this dev box.
**Option B — pin `torch>=2.2.2,<2.3` (chosen).** Keeps the lock resolvable on
both macOS-x86_64 and linux/amd64. CPU build; spaCy falls back to CPU as before.

### Migrations on deploy

Entrypoint `alembic upgrade head` then `exec` the server (chosen) vs. a separate
one-shot `migrate` compose service. The entrypoint is idempotent, needs no
orchestration ordering beyond `depends_on: db healthy`, and verified as a no-op
on the second start.

---

## Tradeoffs

- **Image weight.** torch (CPU) + the transformer model add hundreds of MB to the
  API image. Accepted for self-host; a multi-stage/cpu-index slim-down is a noted
  follow-up, not in 033's acceptance.
- **`VITE_API_BASE_URL` is build-time.** Changing the public API origin requires
  rebuilding the webapp image, not just a restart. Documented; the cost of Vite
  inlining `import.meta.env`.
- **Single-stage webapp image.** Ships source + full `node_modules` rather than a
  pruned runtime. Chosen for module-resolution correctness (the built handler
  imports bare packages at runtime); leaner multi-stage is a follow-up.
- **No TLS / reverse proxy / external DB / deploy CI.** Deliberately out of scope
  (spec Non-Goals); compose exposes plain HTTP and the operator terminates TLS
  upstream.

---

### Spec Divergence

| Spec Said | What Was Built | Reason |
|---|---|---|
| Add `spacy-transformers` | Added `spacy-curated-transformers` | The model's `meta.json` requires the curated backend; `spacy-transformers` is the wrong package. |
| "Nitro node-server Dockerfile + production start"; run `node dist/server/server.js` | `srvx` adapter `webapp/server.mjs` (`node server.mjs`) | This TanStack Start version emits a fetch handler, not a Nitro listener — the direct run binds nothing. |
| (plan) `torch` unconstrained | `torch>=2.2.2,<2.3` | Keep the cross-platform lock resolvable (no macOS-x86_64 wheels after 2.2.2). |
| Smoke: "process a short video end-to-end" for the 030 gate | Ran the real `FraseExerciseGeneratorService` in-container on sample segments | Same code path (model load → blank selection → hints), deterministic, no multi-minute YouTube download/transcription. Full pipeline endpoints already covered by the backend suite. |
| Smoke: recordings persist via POST→down→up→playback | Volume-sentinel survives a full `down`→`up` recreate | The upload/playback round-trip is already covered by `test_recording_routes.py`; the *acceptance criterion* is volume durability, which the sentinel proves directly. |
| (not in spec) | Added `YOUTUBE_API_KEY` to `.env.example`; added `webapp/` to root `.dockerignore` | Pre-existing doc gap (`config.py` requires the key); keep the API build context from pulling `webapp/node_modules`. |

Everything else matched the spec: env-driven CORS with dev default, migrate-on-deploy
entrypoint, recordings named volume, three-service compose, build-time
`VITE_API_BASE_URL`, and the documented public-origin contract.

---

## Spec Gaps Exposed

- **ARCHITECTURE.md is stale on the frontend server.** It calls the frontend a
  "Vite Nitro React" / "nitro web server" app. The pinned TanStack Start emits a
  srvx-served fetch handler, no Nitro. → candidate ARCHITECTURE.md revision.
- **`.env.example` was missing `YOUTUBE_API_KEY`** despite `config.py` raising
  without it. Fixed here; worth a general "does `.env.example` match
  `config.py`?" check in future audits.
- **Two independent `es_dep_news_trf` load paths** remain (`spanish_nlp.get_nlp()`
  singleton vs. the per-instance `spacy.load` in `FraseExerciseGeneratorService`).
  Out of scope for 033 (both work once the model is installed), but a noted
  cleanup candidate.

---

## Test Evidence

**Backend suite (local, Postgres fixture) — 140 passed** (134 prior + 6 new
`ALLOWED_ORIGINS` parser tests):

```
$ uv run pytest
140 passed, 398 warnings in 12.64s
```

**`uv sync --frozen` pulls the model from the locked wheel; loads cleanly:**

```
$ uv sync --frozen
Audited 170 packages in 0.07ms
$ uv run python -c "import spacy; print(spacy.load('es_dep_news_trf').pipe_names)"
['transformer', 'morphologizer', 'parser', 'attribute_ruler', 'lemmatizer']
```

**Prod-mode Docker Compose smoke (daemon 29.4.0) — all gates:**

```
# Build
 Image comprende-ya-api Built
 Image comprende-ya-webapp Built

# Migrate on cold pgdata volume (first start)
api-1 | [entrypoint] alembic upgrade head
api-1 | INFO [alembic.runtime.migration] Running upgrade  -> 1b329637734b, baseline schema
api-1 | INFO [alembic.runtime.migration] Running upgrade 1b329637734b -> 8e95de50f88f, add profile + study_session tables
api-1 | [entrypoint] starting FastAPI on 0.0.0.0:8000

# 030 gate — real exercises generated INSIDE the api container
exercises generated: 2
{
  "exercise_text": "Si ___más tiempo, ______toda Latinoamérica ___mis amigos.",
  "answers": { "blank_0": "por", "blank_1": "tuviera", "blank_2": "viajaría", "blank_3": "con" },
  "hints":   { "blank_0": "preposición", "blank_1": "verbo", "blank_2": "verbo", "blank_3": "preposición" }
}

# CORS — env-driven
allowed  http://localhost:3000  -> access-control-allow-origin: http://localhost:3000
bogus    http://evil.example    -> (no ACAO header) — correctly rejected

# Webapp — served + build-time origin baked in
webapp / -> HTTP 200
dist/client/assets/api-C0avKHAD.js: 1 × http://localhost:8000

# Recordings volume persists across full down→up recreate
persist-me-033  -> RECORDINGS PERSISTED

# Idempotent migrations on second start (DB already at head)
$ docker compose logs api | grep -c "Running upgrade"
0
api-1 | INFO Application startup complete.
api-1 | INFO Uvicorn running on http://0.0.0.0:8000
```

**Frontend:** `pnpm lint` (biome, 33 files) clean · `pnpm typecheck` clean ·
`pnpm build` green · `node server.mjs` (srvx) serves the real SSR app (HTTP 200).
