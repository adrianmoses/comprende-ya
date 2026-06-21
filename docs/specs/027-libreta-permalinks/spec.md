# Spec: La Libreta permalinks (stable resource deep-links)

| Field | Value |
|---|---|
| id | 027 |
| status | approved |
| created | 2026-06-21 |

---

## Why

La Libreta is the operator's daily study planner. When it surfaces a listening
suggestion, it wants to deep-link the user straight into the matching ComprendeYa
resource — "Open in ComprendeYa" should land Ana on the actual video, player
ready, not on a search page. La Libreta's feature 012 (deep-links) calls this out
as a prerequisite: ComprendeYa must expose **stable permalinks** that La Libreta
can hardcode in its content seed.

The input contract lives in La Libreta's repo at
`docs/specs/012-deep-links/companion-interface.md` (§ ComprendeYa). This spec is
ComprendeYa's side of that contract.

**The central finding: ComprendeYa already satisfies the permalink contract.**
The companion doc was written before auditing ComprendeYa's code and assumed we'd
need to invent slugs, add a `/resource/:id` route, and gate it behind
login-then-redirect. None of that is true here:

- The stable id already exists — it's the **YouTube id** (`m1DFpkNdcv0`), the
  natural primary key for every resource in the catalog.
- The permalink route already exists — `GET /api/videos/{video_id}` is
  docstringed *"Obtener video procesando por ID (permalink)"* and the frontend
  `/listen/$id` route renders it.
- Unknown ids already 404 (API `HTTPException(404)` → frontend `<NotFound>` with
  "Volver a Inicio") — no silent redirect to search.
- A discovery endpoint already exists — `GET /api/videos/` lists every resource
  with its `video_id`.
- There is no auth gate (single-user deployment, CORS-only) — the
  login-then-redirect dance from the companion doc is moot.

So this spec is mostly **ratify, harden, and document** rather than build. The
one genuinely new bit of work is making the discovery endpoint safe for La
Libreta's build-time validation (today it silently caps at 20 rows).

### Consumer Impact

- **La Libreta (the operator's other app).** Gains a reliable URL scheme to pin
  in its seed. La Libreta adds `comprendeYaId?: string` to its `Content` rows and
  builds `${COMPRENDEYA_BASE_URL}/listen/{comprendeYaId}`. The value it stores is
  a YouTube id, copied by hand from ComprendeYa's catalog when the operator
  curates a listening item.
- **Ana, the learner.** Clicking "Open in ComprendeYa" in La Libreta lands her on
  the real Escuchando screen for that video. No behaviour change inside
  ComprendeYa itself — this is the same `/listen/$id` view 015 shipped.
- **Future ComprendeYa contributors.** Get a documented "YouTube ids are an
  external contract — never reuse or hand-rewrite them" rule so a later refactor
  doesn't quietly break La Libreta's pinned links.

### Roadmap Fit

- **Depends on:** 008 (video CRUD — `GET /api/videos/{id}` and `GET /api/videos/`
  both already shipped), 015 (Escuchando `/listen/$id` route + 404 state).
- **Unblocks:** La Libreta 012 deep-link wiring (separate repo).
- **Doesn't block:** anything in this repo. Nothing here depends on 027.

---

## What

### The contract, stated plainly

| Concern | Contract | Status today |
|---|---|---|
| Stable id | The **YouTube id** (`videos.youtube_id`) is the permalink id. | ✅ exists |
| User-facing route | `GET /listen/{youtube_id}` (frontend) renders the resource in the player. | ✅ exists (015) |
| API permalink | `GET /api/videos/{youtube_id}` returns the resource payload. | ✅ exists (008) |
| Unknown id | HTTP 404 from the API; friendly `<NotFound>` page on the frontend. **No redirect to search.** | ✅ exists |
| No reuse / no GC | A published id must never point at different content. | ✅ inherent (see Key Decisions) |
| Discovery | A way for La Libreta to enumerate valid ids at build time. | ⚠️ exists but caps at 20 |
| Auth survival | If gated, login-then-redirect. | n/a — no auth |

### Acceptance Criteria

- [ ] **Documented contract.** The README (and/or `docs/specs/ARCHITECTURE.md`)
  states that `youtube_id` is the external permalink identifier consumed by La
  Libreta, that `/listen/{youtube_id}` is the stable user-facing route, and that
  ids must never be reused or hand-edited. This is the substance of the feature —
  the guarantee is only real once it's written down where a future contributor
  will see it.
- [ ] **Seed validation is truncation-safe.** La Libreta can confirm its pinned
  ids resolve without being misled by the existing `GET /api/videos/?limit=20`
  cap (which would let a seed-validation run pass against a partial list, then ship
  a "valid" id that 404s). Met by `POST /api/videos/exists` (OQ1 → (d)): the check
  is bounded by the request, so there is nothing to truncate.
- [ ] **404 behaviour confirmed and guarded by a test.** `GET /api/videos/{bogus}`
  returns 404 (already true) — add/keep a test so a future change can't soften it
  into a 200-with-empty or a redirect.
- [ ] **No regression to `/listen/$id`.** The existing Escuchando route and its
  `<NotFound>` state continue to work; this spec must not touch the player.
- [ ] `uv run pytest` green; `uv run ruff check` / `ruff format` clean. If the
  discovery change touches the webapp, `pnpm lint` / `typecheck` / `build` clean.

### Non-Goals

- **Inventing slugs.** The companion doc *recommends* human-readable slugs
  (`no-hay-tos-modismos-mexicanos`) over auto-increment integers. That
  recommendation was written against a generic catalog. ComprendeYa is
  YouTube-native: the YouTube id is already short, globally unique, externally
  owned, and deterministic on re-import. Adding a parallel slug column would be
  pure overhead with a second thing to keep stable. We use the YouTube id and
  override the recommendation explicitly (see Key Decisions). The id is opaque to
  La Libreta either way.
- **Changing the route shape to `/resource/:id` or `/episode/:id`.** The companion
  doc says "pick one and commit." ComprendeYa already committed to `/listen/$id`
  in 015. La Libreta builds whatever path we publish; it does not require a
  specific word. We keep `/listen/`. (Cross-repo note below covers aligning the
  companion doc.)
- **Auth / login-then-redirect.** ComprendeYa has no auth (single-user, CORS-only
  per `src/main.py`). The `?redirect=` round-trip in the companion doc is moot. If
  auth is ever added (no current plan), revisit so deep-links survive it.
- **A completion callback to La Libreta.** Habla POSTs back to a `callbackUrl` so
  La Libreta can auto-stamp the speaking activity. The companion doc deliberately
  makes ComprendeYa **read-only / reference-only** — no token, no callback, no
  server-to-server contract. If listening-completion auto-stamping is wanted later
  it's a separate, larger spec (ComprendeYa would need a shared token + a callback
  on MCQ-session completion), not part of permalinks. Left out on purpose.
- **A timestamp deep-link as a new feature.** `/listen/$id?t={seconds}` already
  exists (added in 020 for jump-to-source). La Libreta *may* append `?t=` if it
  ever wants to land mid-video, but no work is required here; noting it so it's
  not "discovered" as missing.
- **Restricting which YouTube videos can be linked.** A permalink only resolves if
  the video has already been processed into ComprendeYa. That ingestion is the
  operator's existing workflow (`POST /api/videos/process-async`), out of scope
  here. La Libreta's seed must only pin ids that already exist — which is exactly
  what the discovery endpoint is for.

### Open Questions

1. **How does La Libreta safely enumerate ids given the 20-row cap?** Options:
   - **(a)** Have La Libreta's build-time validator paginate `GET /api/videos/`
     via `skip`/`limit` until a short page returns. Zero ComprendeYa change, but
     pushes pagination correctness onto the consumer and is fragile (off-by-one,
     concurrent inserts). The discovery list is small and slow-changing, so the
     race is mostly theoretical.
   - **(b)** Add a thin `GET /api/videos/ids` returning `["m1DFpkNdcv0", …]`
     (or `[{id, title}]`) with no pagination — purpose-built for seed validation.
     A few lines on top of `VideoRepository.list` with no `limit`.
   - **(c)** Raise/disable the cap only when an explicit `limit=0`/`all=true` is
     passed to the existing endpoint.
   - **(d)** Add a multi-get / batch-existence endpoint and have La Libreta send
     the exact ids it pinned, e.g. `POST /api/videos/exists` with
     `{ "ids": ["abc123", …] }` → `{ "present": [...], "missing": [...] }`. This
     **inverts** the check: instead of enumerating ComprendeYa's whole catalog and
     filtering client-side (a, b, c), La Libreta pushes its ~20 seed ids and asks
     "which of these resolve?" — the membership test the validation actually is.
     Transfer scales with **seed size, not catalog size**; no pagination concern at
     all; and the server returns `missing` directly, so a failing build names the
     rotted id with zero client logic. Costs a POST-for-a-read and slightly more
     endpoint semantics than (b)'s dumb id dump.

   **Recommendation: (b) for ComprendeYa's scale, (d) if you prefer the
   contract to read "ask whether *these* resolve."** (b) makes the set explicit and
   self-documenting, keeps the consumer dumb, avoids overloading the human-facing
   list endpoint (paginated for good reason on Inicio), and at a single-operator
   catalog of dozens of videos its catalog-sized transfer is trivially cheap — so
   (d)'s seed-size scaling advantage is theoretical here. (d) is the cleaner
   *semantic* fit for validation and the better choice if the catalog ever grows
   large or you want the rotted id named server-side; it is not over-engineering,
   just earlier than the scale needs it. Both are one small repository method +
   route + test. Avoid (a) (pushes fragile pagination onto the consumer) and (c)
   (overloads the Inicio endpoint with a second mode). Decide before implementing.

2. **Should the API 404 page and the frontend `<NotFound>` say anything about the
   source being La Libreta?** Recommendation: **no.** The permalink is anonymous —
   ComprendeYa can't (and shouldn't) know the click came from La Libreta. The
   existing generic "Video no encontrado" / "Volver a Inicio" is correct. The
   *loud* failure is what La Libreta's build-time validation is for; a rotted id
   should be caught before it ships, not explained at click time.

3. **Where does the contract documentation live — README, ARCHITECTURE.md, or a
   `CONTRIBUTING` note?** Recommendation: a short "External contract: La Libreta
   permalinks" section in `docs/specs/ARCHITECTURE.md` (the architectural
   invariant) plus a one-line pointer in README. ARCHITECTURE.md is where a
   contributor reasoning about the `videos` schema will look before renaming or
   re-keying anything.

---

## How

### Approach

Most of the work is verification + documentation; the only code is the discovery
endpoint (pending OQ1).

#### 1. Batch-existence endpoint (OQ1 → (d))

La Libreta validates its seed by pushing the exact ids it pinned and asking which
resolve — a membership test, not an enumeration. `src/api/routes/videos.py`:

```python
@router.post("/exists")
async def check_videos_exist(req: VideoExistsRequest, db: Session = Depends(get_session)):
    """Contrato de permalinks con La Libreta — comprobación de existencia por lote.

    La Libreta envía los youtube_ids fijados en su seed y recibe cuáles resuelven.
    El transporte escala con el tamaño del seed, no del catálogo, y `missing`
    nombra los ids podridos directamente. Ver docs/specs/027-libreta-permalinks.
    """
    repo = VideoRepository(db)
    present = set(repo.existing_youtube_ids(req.ids))
    return {
        "present": [i for i in req.ids if i in present],
        "missing": [i for i in req.ids if i not in present],
    }
```

`src/models/schemas.py` — add the request schema:

```python
class VideoExistsRequest(BaseModel):
    ids: list[str]
```

`src/repositories/` — add `existing_youtube_ids(ids: list[str]) -> list[str]`: a
single `select(Video.youtube_id).where(Video.youtube_id.in_(ids))`. Project the
id column only — no row hydration, no relationship loading. One round trip
regardless of how many ids are sent; the `IN` set is bounded by the request, so no
pagination concern. Preserve the caller's order and dedupe defensively if the seed
ever sends duplicates (the dict-comprehension-over-`req.ids` above already does).

> **Route ordering:** unlike a `GET /ids` enumeration, `POST /exists` does **not**
> collide with the `GET /{video_id}` catch-all — different method, and there is no
> `POST /{video_id}` single-segment route to shadow it (`POST /{video_id}/progress`
> et al. all require a sub-segment). So placement is safe anywhere in the router.
> Still add a test that `POST /api/videos/exists` returns 200 with `present` /
> `missing`, to lock the contract against a future refactor.

#### 2. Confirm/lock the 404 contract

`GET /api/videos/{bogus}` already raises `HTTPException(404)` (videos.py:228) and
the frontend already renders `<NotFound>` for `error.message.startsWith("404")`
(listen.$id.tsx:54,264). Add a backend test asserting the 404 if one doesn't
already exist in `tests/` so it can't regress to a redirect or empty-200.

#### 3. Document the contract

Add to `docs/specs/ARCHITECTURE.md` (new short section) and README:

> **External contract — La Libreta permalinks.** `videos.youtube_id` is the
> stable public identifier for every resource. La Libreta (the operator's study
> planner) hardcodes these ids in its content seed and builds deep-links of the
> form `${COMPRENDEYA_BASE_URL}/listen/{youtube_id}`. Therefore:
> - **Never reuse a `youtube_id`** for different content. (Inherently safe —
>   YouTube ids are externally owned and globally unique; re-importing the same
>   video yields the same id.)
> - **Never rewrite or alias** existing ids in a migration.
> - `GET /listen/{id}` and `GET /api/videos/{id}` must keep resolving, and must
>   **404 — not redirect** — on unknown ids.
> - `POST /api/videos/exists` is the batch-existence endpoint La Libreta validates
>   its seed against (sends its pinned ids, gets back `present` / `missing`); keep
>   it returning every requested id's status with no truncation.

#### 4. Cross-repo follow-up (not code in this repo)

La Libreta's `docs/specs/012-deep-links/companion-interface.md` currently
describes ComprendeYa with the wrong assumptions (slugs, `/resource/:id`,
login-redirect, optional `GET /api/resources`). Once this spec is approved, that
doc should be updated to the real contract: id = YouTube id, route = `/listen/`,
seed validation = `POST /api/videos/exists`, no auth. Tracked as a La Libreta-side
edit; noted here so the two repos don't drift.

### Confidence

**Level:** High

**Rationale:** The permalink, the route, and the 404 all already exist and are
exercised by 015's Escuchando screen and 008's CRUD. The only new surface is the
`POST /api/videos/exists` batch check — a near-trivial repository method
(`select … where youtube_id in (…)`) + route + schema, with no pagination or
route-ordering gotcha to manage. The rest is documentation. No external-service,
AI, or migration risk.

**Validate before proceeding:** OQ1 is resolved to **(d)** — the batch-existence
endpoint. The remaining decisions (OQ2 404 copy, OQ3 doc location) don't change
whether code ships.

### Key Decisions

- **The YouTube id is the permalink contract id — not a new slug.** It is already
  stable, unique, short, externally owned, and deterministic on re-import.
  Inventing a slug column would add a second identifier to keep eternally stable
  for zero consumer benefit (La Libreta treats the id as opaque). This is a
  deliberate override of the companion doc's slug recommendation, which assumed a
  catalog without a natural stable key. ComprendeYa has one.
- **No-GC / no-reuse is satisfied by construction.** There is no
  `DELETE /api/videos/{id}` endpoint, and a YouTube id can never be reassigned to
  different content upstream. The only rot vector is a contributor manually
  re-keying rows in a migration — which the documentation explicitly forbids.
- **Keep `/listen/$id`; do not add `/resource/:id`.** The route word is ours to
  choose and was committed in 015. La Libreta builds whatever path we publish.
- **Read-only / reference-only — no callback, no token.** Matches the companion
  doc's intent for ComprendeYa. Listening-completion auto-stamping, if ever
  wanted, is a separate spec, not a permalink concern.
- **Seed validation is a batch-existence endpoint (`POST /api/videos/exists`),
  not an enumeration or an overloaded list param.** It models the actual question
  — "do *these* pinned ids resolve?" — so transfer scales with the seed, not the
  catalog, the server returns `missing` directly, and the human-facing paginated
  `GET /api/videos/` stays clean. (OQ1 → (d); the `GET /ids` enumeration was the
  runner-up and is the fallback if a whole-catalog listing is ever wanted.)

### Testing Approach

Consistent with the repo's pytest bar (025):

- **`tests/` — backend:**
  - `GET /api/videos/{bogus}` → 404 (lock the contract).
  - `POST /api/videos/exists` with a mix of one seeded `youtube_id` and one bogus
    id → 200, correctly partitions into `present` / `missing`, and preserves the
    requested-id order.
  - `POST /api/videos/exists` with `{ "ids": [] }` → 200 with empty `present` /
    `missing` (no crash on the empty `IN`).
  - `POST /api/videos/exists` with more ids than the old `limit=20` cap, all
    seeded → all land in `present` — proves no silent truncation.
- **Manual smoke:** with the backend + webapp up, hit
  `http://localhost:3000/listen/m1DFpkNdcv0` (a seeded id) → Escuchando renders;
  hit `/listen/zzzz-bogus` → `<NotFound>` + "Volver a Inicio".
- **Decision record** at `027-libreta-permalinks/decision.md` capturing: the
  final `POST /api/videos/exists` request/response shape as shipped, any deviation
  from the OQ1 → (d) sketch, and confirmation that the companion-interface.md
  update landed in the La Libreta repo.
