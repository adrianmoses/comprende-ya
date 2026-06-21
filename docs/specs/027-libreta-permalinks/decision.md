# Decision Record: La Libreta permalinks (stable resource deep-links)

| Field | Value |
|---|---|
| id | 027 |
| status | implemented |
| created | 2026-06-21 |
| spec | [spec.md](./spec.md) |

---

## Context

La Libreta (the operator's Spanish-study planner, a separate repo) deep-links its
listening suggestions into ComprendeYa by pinning ComprendeYa's resource ids in
its content seed and building `${COMPRENDEYA_BASE_URL}/listen/{id}` URLs. The
prerequisite was a way for La Libreta to validate, at build time, that its pinned
ids still resolve — otherwise a rotted id ships silently and 404s in front of the
user.

The spec's central finding (from auditing the codebase before writing) was that
ComprendeYa **already** satisfies the permalink contract: the YouTube id is the
stable identifier, `GET /api/videos/{id}` is docstringed "(permalink)" and is
rendered by the `/listen/$id` route (015), unknown ids already 404, and there is
no auth gate to survive. The only genuine gap was discovery: `GET /api/videos/`
silently caps at `limit=20`, so a seed-validation run could pass against a partial
list and then ship an id that 404s.

So this feature was small by design — one new endpoint plus ratifying the contract
in docs and locking the 404 with a test. It was implemented directly against the
spec's §How sketch with no surprises.

## Decision

Added `POST /api/videos/exists` — a batch-existence check. La Libreta sends the
exact ids it pinned (`{"ids": [...]}`) and gets back `{"present": [...],
"missing": [...]}`, both echoing the requested order. This models the actual
question ("do *these* ids resolve?") as a membership test, so transfer scales with
the seed rather than the catalog and the response is bounded by the request — there
is nothing to truncate.

The YouTube id was ratified as the permalink contract id (no new slug column), and
the no-reuse / 404-not-redirect guarantees were documented in `ARCHITECTURE.md`
(new "External Contracts" section) and `README.md`. A regression test locks the
permalink-miss 404.

---

## Alternatives Considered

### How La Libreta enumerates valid ids past the 20-row cap (spec OQ1)

**Option A — La Libreta paginates `GET /api/videos/`.**
- Pros: zero ComprendeYa change.
- Cons: pushes pagination correctness onto the consumer; fragile (off-by-one,
  concurrent inserts); still catalog-sized transfer.

**Option B — `GET /api/videos/ids` enumeration (whole catalog, unpaginated).**
- Pros: dumb GET, cacheable; one small repo method.
- Cons: transfer scales with the catalog, not the seed; client must reconstruct
  the membership test; has a FastAPI route-ordering trap (`/ids` must precede the
  `GET /{video_id}` catch-all).

**Option C — overload `GET /api/videos/` with `limit=0`/`all=true`.**
- Pros: no new route.
- Cons: gives the human-facing list endpoint a second mode; easy to misuse.

**Option D — `POST /api/videos/exists` batch existence.**
- Pros: answers the real question directly; seed-sized transfer; no pagination;
  server returns `missing` so a failing build names the rotted id with no client
  logic; a `POST /exists` cannot be shadowed by `GET /{video_id}`.
- Cons: POST-for-a-read; slightly more endpoint semantics than a dumb id dump.

**Chosen: D.** It is the cleanest semantic fit for validation. The user
explicitly selected it after the trade-off was recorded in OQ1. B remains the
documented fallback if a whole-catalog listing is ever needed.

### Identifier: YouTube id vs. an invented slug

**Option A — invent a human-readable slug column** (the companion doc's original
recommendation).
- Pros: human-readable in La Libreta's seed.
- Cons: a second identifier to keep eternally stable, for zero consumer benefit
  (La Libreta treats the id as opaque).

**Option B — use the existing `youtube_id`.**
- Pros: already the primary key; short; globally unique; externally owned;
  deterministic on re-import — strictly better for the no-reuse guarantee.
- Cons: none material.

**Chosen: B.** The companion doc's slug recommendation assumed a catalog without a
natural stable key; ComprendeYa has one. The companion-interface.md in the La
Libreta repo was updated to reflect this.

---

## Tradeoffs

- **POST for a read.** `POST /api/videos/exists` is a read masquerading as a POST
  because the id set travels in the body. Accepted: it keeps the request bounded
  and avoids URL-length limits on large id sets, and the semantics ("ask whether
  these resolve") are clear.
- **Order-preserving comprehensions over a set.** The handler builds a `set` for
  O(1) membership then iterates `request.ids` twice to partition. This dedupes
  defensively and preserves caller order at the cost of two linear passes —
  negligible for seed-sized inputs.
- **No completion callback / no token.** ComprendeYa stays read-only/reference-only
  to La Libreta (unlike Habla's session push). Listening-completion auto-stamping,
  if ever wanted, is a separate, larger feature — deliberately not built.
- **Whole-catalog enumeration not provided.** Anything that needs to *browse* all
  ids (vs. validate a known set) is unserved until B is added. No current consumer
  needs it.

---

### Spec Divergence

The implementation matches the spec. OQ1 was resolved to option (d) — the path the
spec's §How was rewritten to commit to — and the endpoint shape, repository method,
route placement, documentation, and tests all match §How and the Testing Approach
as written. No divergences.

| Spec Said | What Was Built | Reason |
|---|---|---|
| (none) | — | Implementation followed the spec as written. |

One cosmetic note: `ruff format` collapsed the handler signature
`check_videos_exist(request, db)` onto a single line (the spec sketch wrapped it
across three). Formatting only; no behavioural difference.

---

## Spec Gaps Exposed

None in this spec. One pre-existing observation, already known and out of scope
here: `GET /api/videos/` defaults to `limit=20` and silently truncates — this
feature routes around it (the batch check is unbounded by pagination) rather than
fixing the list endpoint. If a whole-catalog enumeration is ever needed, that cap
and OQ1 option (b) are the place to revisit.

---

## Test Evidence

Five tests added to `tests/test_videos_routes.py`:

- `test_videos_exists_partitions_present_and_missing`
- `test_videos_exists_preserves_requested_order`
- `test_videos_exists_empty_ids`
- `test_videos_exists_no_truncation_past_list_cap` (seeds 25 videos > the 20-row cap)
- `test_video_permalink_miss_returns_404`

Videos route file (6 prior + 5 new):

```
$ uv run pytest tests/test_videos_routes.py -p no:warnings
...........                                                              [100%]
11 passed in 6.91s
```

Full suite — no regressions:

```
$ uv run pytest -p no:warnings
........................................................................ [ 70%]
..............................                                           [100%]
102 passed in 7.84s
```

Lint / format clean:

```
$ uv run ruff check src/ tests/
All checks passed!

$ uv run ruff format --check src/ tests/
48 files already formatted
```
