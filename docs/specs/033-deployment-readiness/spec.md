# Spec: Deployment Readiness — externalize config + ship both services

| Field | Value |
|---|---|
| id | 033 |
| status | implemented |
| created | 2026-06-29 |

---

## Why

The app runs on `localhost` but is **not deployable**. A deploy-readiness audit
(ROADMAP, 2026-06-28) found five blockers that each prevent a real deployment
from working, plus the absence of any production artifact for the frontend:

1. **Backend CORS is hardcoded** to three `localhost:3000` variants in
   `src/main.py` — a deployed webapp on any other origin is rejected by the browser.
2. **The Docker image can't generate exercises.** The image runs only
   `uv sync --frozen`, but spaCy's `es_dep_news_trf` model (and its `torch`
   dependency) live *outside* `uv.lock` — so `FraseExerciseGeneratorService`
   fails at model load in-container. This is item **030**, folded into 033.
3. **No migrations on deploy.** Nothing runs `alembic upgrade head`; a fresh
   database comes up with no schema.
4. **`recordings/` sits on ephemeral container disk.** Every redeploy/restart
   silently loses the learner's speaking-prompt audio (feature 021).
5. **No frontend production server.** The webapp has a TanStack Start (Nitro)
   build but no Dockerfile, no production start command, and `VITE_API_BASE_URL`
   is a build-time value that defaults to `localhost:8000`.

033 closes all five so the operator can stand up the full product — backend +
frontend + database — on a single self-hosted host with one command, with audio
that survives restarts and config that comes from the environment.

### Consumer Impact

- **The operator (primary).** Today "deploy" is impossible without hand-editing
  source. After 033: `docker compose up` against a `.env` file brings up api +
  webapp + postgres, runs migrations automatically, persists recordings, and
  honors environment-driven origins. The smoke is reproducible locally before
  any host is touched.
- **The single B2 learner.** Gets an app reachable at a stable origin (not
  `localhost`) whose exercise generation actually works in-container and whose
  recordings don't vanish.
- **La Libreta (downstream contract).** Its deep-links
  `${COMPRENDEYA_BASE_URL}/listen/{youtube_id}` must resolve against the deployed
  origin. 033 makes that origin real and configurable; the `youtube_id` resolve/
  404 contract (027, ARCHITECTURE "External Contracts") is unchanged.

### Roadmap Fit

- **Folds in 030** (track `es_dep_news_trf` + `torch` as managed deps). 030 was
  filed as the root cause of in-container exercise breakage; 033 needs a working
  image, so it absorbs 030's dependency work and marks 030 implemented.
- **Builds on 012/029.** Flow status is already DB-backed (`processing_jobs`,
  012) and the schema baseline is Postgres-native and trustworthy (029) — so
  "run migrations on deploy" is a clean `alembic upgrade head`, not a drift fight.
- **Depends on 021's storage shape.** `RECORDINGS_DIR` is already env-driven
  (`config.py:34`); 033 supplies the durable volume behind it.
- **Independent of 032/034.** Those are frontend-feature wiring; 033 is
  infrastructure and can ship in parallel. 033 does **not** depend on 032.

---

## What

### Acceptance Criteria

From the operator's perspective, after 033:

- [ ] **One command stands up the stack.** `docker compose up` (with a populated
      `.env`) brings up three services — `api`, `webapp`, `db` (Postgres) — and
      the app is reachable end-to-end.
- [ ] **CORS is environment-driven.** The backend reads allowed origins from an
      `ALLOWED_ORIGINS` env var (comma-separated). The hardcoded `localhost:3000`
      list is gone. With `ALLOWED_ORIGINS` unset, dev defaults to
      `http://localhost:3000` so local `pnpm dev` still works.
- [ ] **Migrations run on deploy.** The api container runs `alembic upgrade head`
      before the server starts (entrypoint/release step); a fresh `db` volume
      comes up fully migrated with zero manual steps.
- [ ] **Exercise generation works in-container.** The api image installs `torch`
      + `es_dep_news_trf`; `FraseExerciseGeneratorService` loads the model and a
      processed video yields fill-in-the-blank exercises inside the container
      (the 030 fix, verified — not assumed).
- [ ] **Recordings survive restarts.** `recordings/` is backed by a named Docker
      volume mounted at `RECORDINGS_DIR`; a recording POSTed before
      `docker compose down && up` is still playable after.
- [ ] **The webapp ships as a production server.** A webapp Dockerfile builds the
      TanStack Start bundle and runs the Nitro node-server; `VITE_API_BASE_URL`
      is injected at **build time** as the API's public origin.
- [ ] **The API public origin is consistent across config.** The same public API
      origin used for `VITE_API_BASE_URL` (browser-reachable) appears in the
      backend's `ALLOWED_ORIGINS`. The docs make explicit that this is the
      *public* origin, **not** the internal compose service name `http://api:8000`.
- [ ] **Required env is documented.** `.env.example` (root) and
      `webapp/.env.example` enumerate every variable the deployment needs, with
      the public-origin contract spelled out. A short deploy section in the README
      describes `docker compose up` and the volume/secret model.
- [ ] **A local prod-mode smoke passes and is recorded** in the decision record:
      compose build + up, migrations applied, CORS honors `ALLOWED_ORIGINS`,
      exercise gen works in-container, recordings persist across a restart, and
      the webapp reaches the api through its public origin.

### Non-Goals

- **No live cloud deployment.** Scope ends at deploy-ready artifacts verified by
  a local prod-mode smoke. No host is provisioned, no credentials are used.
- **No managed Postgres / external DB.** Postgres is a compose service on a named
  volume. Pointing `DATABASE_URL` at a managed DB is supported by config but not
  delivered or tested here.
- **No TLS / reverse proxy / domain config.** The operator terminates HTTPS
  upstream (Caddy/nginx/Cloudflare). Compose exposes plain HTTP ports; the
  `ALLOWED_ORIGINS` / `VITE_API_BASE_URL` contract is documented so TLS can sit
  in front without code changes.
- **No deploy CI.** The roadmap's "(optional) deploy CI" is dropped under the
  deploy-ready-artifacts scope. Existing test CI is untouched.
- **No multi-worker / horizontal scale.** The single-process `BackgroundTasks`
  flow constraint stands (ARCHITECTURE "Key Constraints"); concurrent processing
  remains a known limitation, not addressed here.
- **No k8s / orchestration beyond compose.**
- **Not fixing unrelated audit warts** (duplicate dialect classifier, legacy sync
  `/process`, 404 message typos). Out of scope.
- **No GPU.** torch installs as the CPU build; spaCy falls back to CPU as it
  already does (`spacy.prefer_gpu()` is best-effort).

### Open Questions

- **Compose port exposure for the smoke.** The local smoke must exercise the
  *public-origin* path (browser → published port), not the internal compose
  network, to actually prove the `VITE_API_BASE_URL` / CORS contract. Resolve at
  implementation: publish api + webapp ports on the host and point
  `VITE_API_BASE_URL` at the published api port for the smoke build. Deferred,
  not blocking.
- **torch image weight.** The CPU torch wheel + `es_dep_news_trf` transformer
  model add hundreds of MB to the api image. Acceptable for self-host; if build
  time/size is painful, a multi-stage build or a prebuilt base is a follow-up
  optimization, not part of 033's acceptance.

---

## How

### Approach

**Backend — `src/main.py` / `src/config.py`**

- Add `ALLOWED_ORIGINS` to `Settings` (comma-separated string → parsed list).
  Default to `http://localhost:3000` (+ the `127.0.0.1` / `0.0.0.0` variants, to
  preserve current dev behavior) when the env var is absent.
- `main.py` builds the `CORSMiddleware` `allow_origins` from
  `settings.ALLOWED_ORIGINS`; delete the hardcoded list.

**Backend — image + migrations (`Dockerfile`)**

- **030 fold-in:** make `torch` (CPU) and `es_dep_news_trf` install reproducibly
  in the image. Preferred: add `torch` as a managed dependency and install the
  spaCy model via its pip wheel URL (a uv-trackable source) so `uv sync --frozen`
  alone produces a working image — solving 030's "uv prunes it" root cause. If
  full lockfile tracking proves impractical, fall back to an explicit
  `uv run python -m spacy download es_dep_news_trf` (+ torch) step in the
  Dockerfile and document the limitation. Either way the acceptance bar is the
  same: exercise generation works in-container.
- **Migrations on deploy:** add an entrypoint script (or compose `command`) that
  runs `alembic upgrade head` and then `exec`s the FastAPI server. Idempotent;
  safe to run every start.
- **Recordings volume:** mount a named volume at `RECORDINGS_DIR` (already
  env-driven at `config.py:34`). No code change beyond ensuring the path is
  honored (it is).

**Frontend — `webapp/` production image**

- Add `webapp/Dockerfile`: install via pnpm, `pnpm build` (client + Nitro server
  bundles → `dist/`), then run the Nitro node-server as the production start.
  `VITE_API_BASE_URL` is a **build arg** (Vite inlines `import.meta.env` at build
  time — already consumed at `webapp/src/lib/api.ts:20`).
- Confirm/define the production start command for the TanStack Start node-server
  output (the bundle under `dist/server`); add a `start` script if missing.

**Orchestration — `docker-compose.yml` (repo root)**

- Three services: `db` (Postgres, named volume `pgdata`), `api` (built from root
  `Dockerfile`, depends_on `db`, mounts `recordings` volume, env from `.env`,
  runs migrate-then-serve), `webapp` (built from `webapp/Dockerfile` with
  `VITE_API_BASE_URL` build arg).
- `.env` supplies secrets (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
  `YOUTUBE_API_KEY`), `DATABASE_URL` (pointing at the `db` service),
  `ALLOWED_ORIGINS`, and the public API origin used for the webapp build arg.

**Docs**

- Extend root `.env.example` (`ALLOWED_ORIGINS`, note on public origin) and
  `webapp/.env.example` (`VITE_API_BASE_URL` build-time semantics).
- Add a "Deploy (self-host)" section to the README: `docker compose up`, the
  `.env` contract, the named-volume model, and the explicit warning that
  `VITE_API_BASE_URL` + `ALLOWED_ORIGINS` must be the **browser-reachable public
  origin**, never the internal compose service name.

### Confidence

**Level:** Medium

**Rationale:** The config externalization (env CORS), the alembic-on-deploy
entrypoint, the recordings volume, and the compose wiring are mechanical and
well-understood — `RECORDINGS_DIR` and `VITE_API_BASE_URL` are *already*
env-driven, and 029 makes `alembic upgrade head` a clean no-drift operation.
The uncertainty is concentrated in three places, all folded-in or
production-first work that has never been exercised:

1. **torch + `es_dep_news_trf` in the image (the 030 root cause).** Whether the
   model can be made fully `uv.lock`-trackable vs needing an explicit download
   step, and the resulting image weight, is unproven.
2. **TanStack Start node-server production start.** The exact start command /
   entry for the Nitro `dist/server` output and that it serves correctly with a
   baked-in `VITE_API_BASE_URL` needs a real build+run.
3. **Migrate-then-serve against the compose Postgres** on a cold volume.

**Validate before proceeding:**

- **Spike 1 — working image:** build the api image with torch + `es_dep_news_trf`
  and confirm `FraseExerciseGeneratorService` loads and a sample segment yields
  exercises *inside the container*. This is the 030 gate; it decides the
  lockfile-vs-explicit-download approach.
- **Spike 2 — webapp prod start:** `pnpm build` then run the node-server bundle
  with a build-time `VITE_API_BASE_URL`; confirm it serves and the client calls
  hit the configured origin.
- **Spike 3 — migrate-on-deploy:** bring up compose against an empty `pgdata`
  volume; confirm `alembic upgrade head` runs once, the server starts, and a
  second `up` is a clean no-op.

### Key Decisions

- **Deploy target = self-host Docker Compose** (api + webapp + postgres, named
  volumes, `.env`). Chosen over Fly/Railway/host-agnostic: concrete, single-
  operator-friendly, fully verifiable locally, no cloud credentials in scope.
- **030 folded into 033** rather than sequenced as a separate prerequisite PR —
  033 needs a genuinely working image, so it owns the dependency fix and marks
  030 implemented. One PR ships a runnable container.
- **Scope = deploy-ready artifacts, not a live deploy** — verified by a local
  prod-mode smoke. Keeps the change reviewable and host-independent.
- **`VITE_API_BASE_URL` is build-time and must be the public origin.** Because
  Vite inlines it and the browser runs client-side, the internal compose service
  name (`http://api:8000`) is wrong; the same public origin feeds
  `ALLOWED_ORIGINS`. This contract is documented, not just coded.
- **No TLS in compose** — operator terminates HTTPS upstream; compose stays plain
  HTTP so the artifact is reverse-proxy-agnostic.

### Testing Approach

Per OVERVIEW, the suite is backend `pytest` (on Postgres, 029 fixture); the
frontend stays manual-smoke. 033 is infrastructure, so verification is
primarily a **prod-mode operational smoke** plus a thin unit test for the one new
piece of branching logic:

- **Unit (pytest):** `ALLOWED_ORIGINS` parsing — comma-separated string →
  origin list; unset → the localhost dev default; whitespace tolerance. This is
  the only new code path with logic worth locking.
- **Operational smoke (recorded in the decision record):**
  1. `docker compose build && docker compose up` against a populated `.env`.
  2. Fresh `pgdata` volume → `alembic upgrade head` runs automatically; server
     starts; a second `up` is a no-op.
  3. Process a short video end-to-end → confirm fill-in-the-blank **exercises are
     generated in-container** (the 030 gate).
  4. POST a recording, `docker compose down && up`, confirm it's still playable
     (volume persistence).
  5. With `ALLOWED_ORIGINS` set to the webapp's published origin, confirm a
     cross-origin browser call succeeds; with a bogus origin, confirm it's
     rejected (CORS honors env).
  6. Webapp built with `VITE_API_BASE_URL` = published api origin reaches the api
     (not the internal service name).
- **Regression:** existing backend suite stays green; `webapp` lint / typecheck /
  build stay green.
