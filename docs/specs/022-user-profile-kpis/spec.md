# Spec: User profile + streak + weekly KPIs

| Field | Value |
|---|---|
| id | 022 |
| status | approved |
| created | 2026-06-28 |

---

## Why <!-- required -->

Inicio (the home screen, item 014) was built with four KPI tiles and a personal
greeting, but three of the four tiles render a literal `—` placeholder and the
greeting hardcodes the name. The screen *looks* like a study dashboard and tells
the learner nothing. 022 lands the real aggregates so the home screen reflects
actual effort: how much they studied this week, whether they're keeping a daily
streak, and how well they're comprehending — the three signals a self-study tool
uses to pull someone back for the next session.

Concretely, today's `KpiGrid` (`webapp/src/routes/index.tsx:147`) shows:

- **Esta semana** → `—` (no listening-time data exists anywhere in the backend)
- **Frases guardadas** → already real (wired to the `GET /api/chunks` count in 020)
- **Racha** → `—`
- **Comprensión** → `—`

and `Greeting` hardcodes `"Buenos días, Ana."`. The design bundle's intended
chrome is `Ana · B2 · Día N`. 022 makes all of this real.

### Consumer Impact <!-- required -->

The single self-directed B2 learner (OVERVIEW "Target Consumer" — single-user, no
auth, CORS pinned to one origin). They benefit directly: the home screen becomes a
mirror of their own study habit instead of dead placeholders. The streak and
weekly-minutes tiles create a light, non-gamified pull to return daily; the
comprehension tile gives an honest accuracy signal across everything they've
answered.

This is the consumer-facing payoff of three already-shipped backend capabilities
(MCQ answer tracking 009, chunk library 019/020) plus one genuinely new signal
(listening time) that nothing has captured until now.

### Roadmap Fit <!-- required -->

014 (Inicio) shipped the KPI tiles as placeholders and its revision note explicitly
deferred the values: *"KPI values stay as `—` / `0` until 022 lands real
aggregates."* 022 is that follow-up. It is sequenced after 029 (schema reset →
Postgres-native baseline, models authoritative) deliberately: 022 adds two new
tables, and 029 made the next table-adding feature build on a trustworthy,
drift-free migration baseline. The single-row `profile` table is also the natural
home for settings that 023 (Tweaks panel: theme, accent, transcript size, level
badges) will later read/write, so 022 establishes that table now and 023 extends
it.

---

## What <!-- required -->

### Acceptance Criteria <!-- required -->

- [ ] On Inicio, **Esta semana** shows real minutes studied in the current
      (Monday-start) week — not `—` — and increases after a listening session.
- [ ] **Racha** shows the current daily study streak (consecutive days up to and
      including today with study activity); breaks to `0`/`1` correctly after a
      missed day.
- [ ] **Comprensión** shows all-time MCQ accuracy as a whole-number percent
      (`round(sum(is_correct)/count(*) · 100)`); renders `—` when no MCQs have been
      answered yet (no divide-by-zero, no `0 %` masquerading as a real score).
- [ ] The greeting renders the profile's real name (default `Ana`), and the topbar
      chrome can show `{level} · Día {N}` from the profile.
- [ ] While a video plays on Escuchando, listening time is reported to the backend
      and accrues into that week's minutes; paused/closed-tab time is **not** counted.
- [ ] `GET /api/profile` returns identity + all computed KPIs in a single round
      trip (so Inicio needs one new fetch, not four).
- [ ] All new backend behavior is covered by pytest running on Postgres (per 029),
      including the empty-data edge cases.

### Non-Goals <!-- required -->

- **No multi-user / auth.** The profile is a single seeded row (`id = 1`). No users
  table, no login, no per-user scoping. (Permanent product position, OVERVIEW.)
- **No ASR / pronunciation scoring.** Listening time is a duration heartbeat only —
  no audio is uploaded or evaluated. (Permanent, OVERVIEW "No audio evaluation".)
- **No gamification beyond the three KPIs + streak.** No XP, badges, achievements,
  level-ups, goals/targets, or push reminders.
- **No historical analytics / charts.** Just the four Inicio tiles and the greeting
  chrome — no per-video history, no week-over-week graphs.
- **No backfill of past listening minutes.** Session tracking starts accruing the
  day it ships; pre-022 listening is unrecoverable (nothing recorded it). Week
  minutes simply starts low. (Comprehension and streak *do* draw on existing
  `AnswerProgress` history — only minutes starts fresh.)
- **Not the 023 Tweaks UI.** 022 ships the `profile` table and a `PUT /api/profile`
  to edit name/level, but the settings panel (theme/accent/transcript size) is 023.
- **No timezone configuration UI.** "Today" / week boundaries use a single fixed
  zone (see Open Questions); a user-facing TZ setting is out of scope.

### Open Questions <!-- optional -->

All three resolved at approval (2026-06-28) with the proposed defaults:

1. **`Día N` meaning.** ✅ Resolved → **current streak length** (single source of
   truth with Racha; `dia == streak` in `ProfileResponse`). The design's `Día 6`
   reads as "day 6 of the run."
2. **Timezone for "today" and "this week."** ✅ Resolved → **UTC** for v1 (single
   user, simplest day/week boundaries). A configurable zone can land with 023; the
   week starts Monday.
3. **Does an MCQ-only day count as an "active day" for the streak?** ✅ Resolved →
   **yes**. An active day is any day with a `study_session` row **or** an
   `AnswerProgress` row, so the streak survives a session where the player heartbeat
   failed but the learner clearly engaged.

---

## How <!-- required -->

### Approach <!-- required -->

Two new tables, one new router (`/api/profile`), and a thin frontend heartbeat.

**Data model** (`src/models/database.py`, one Alembic migration regenerated from
the models per the 029 authoritative-models discipline):

- `profile` — singleton identity. `id` (PK, always 1), `name` (default `"Ana"`),
  `level` (default `"B2"`), `created_at`. Seeded with the default row *in the
  migration* so the app never has to handle a missing profile.
- `study_session` — append-only listening log. `id` (PK), `seconds` (int, > 0),
  `created_at` (indexed). One row per reported heartbeat interval. Week minutes =
  `sum(seconds) / 60` over rows whose `created_at` falls in the current week.

**Repository** (`src/repositories/profile_repository.py`) takes a `Session` (repo
pattern, per ARCHITECTURE) and exposes:

- `get_profile()` → the singleton row.
- `update_profile(name, level)` → for `PUT`.
- `add_session(seconds)` → append a `study_session`.
- `week_minutes()` → `SUM(seconds)` for `created_at >= start_of_current_week`,
  integer minutes.
- `comprehension()` → `(correct, total)` from `AnswerProgress` (all-time);
  caller renders `None` when `total == 0`.
- `streak()` → fetch the set of distinct active days (`study_session.created_at`
  ∪ `AnswerProgress.answered_at`, date-truncated), then walk backward from today
  counting consecutive days. Small data; compute in Python rather than a recursive
  CTE for clarity.

**Routes** (`src/api/routes/profile.py`, new router mounted at `/api/profile`):

- `GET /api/profile` → `ProfileResponse { name, level, dia, week_minutes, streak,
  comprehension }` where `comprehension` is `int | null` (percent, null = no data).
  Single round trip for Inicio's greeting + three live tiles.
- `POST /api/profile/session` `{ seconds: int }` → `204`. Called by the Escuchando
  heartbeat. Rejects non-positive / absurd values (clamp/validate).
- `PUT /api/profile` `{ name?, level? }` → updated `ProfileResponse`. Exists for
  editability (023); no UI shipped here beyond what already binds the greeting.

Schemas live in `src/models/schemas.py` (`ProfileResponse`, `SessionRequest`,
`ProfileUpdateRequest`).

**Frontend** (`webapp/`):

- *Inicio* (`routes/index.tsx`): add a `["profile"]` react-query against
  `GET /api/profile`. `KpiGrid` fills **Esta semana** (`week_minutes`, formatted as
  `42 min` / `1 h 12 min`), **Racha** (`streak`), **Comprensión**
  (`comprehension == null ? "—" : `${comprehension} %``). `Frases guardadas` keeps
  its existing chunks-count wiring (unchanged). `Greeting` reads `profile.name`.
- *Escuchando* (`routes/listen.$id.tsx` + the `useYouTubePlayer` hook from 015): a
  heartbeat that accumulates **only PLAYING time**. Accumulate elapsed wall-time
  while the IFrame player state is `PLAYING`; flush to `POST /api/profile/session`
  on a fixed interval (e.g. every 30 s of accrued play) and on pause/unmount.
  Reuses the player-state machinery already built in 015. After a successful flush,
  invalidate `["profile"]` so a later Inicio visit reflects it (no need to live-update
  the current screen).

### Confidence <!-- required -->

**Level:** Medium

**Rationale:** The backend is well-understood — two small tables and aggregate SQL
over data we already store (`AnswerProgress`) plus a trivial append log. Comprehension
and the empty-state handling are straightforward; streak is a short backward walk over
a distinct-days set. The real uncertainty is the **frontend listening heartbeat**:
accurately accumulating *playback* time (not wall-clock) without double-counting across
seeks, pauses, background tabs, or component remounts. This is the same class of
"fire-the-effect-correctly-against-the-IFrame-player" problem that 015 flagged as a
spike, so the risk is known and contained to one hook.

A secondary uncertainty is the streak's "active day" definition and timezone (Open
Questions 1–3) — cheap to decide, but they change observable behavior, so they're
called out rather than assumed silently.

**Validate before proceeding:**

1. **Heartbeat spike** (~30 min on `localhost`): instrument the 015 player hook to
   accumulate PLAYING-state seconds, log flushes, and confirm that play → pause →
   seek → play → close produces a sum that matches actual watched time within a small
   tolerance (no double-count on seek, no accrual while paused). Rises to High after.

   (Open Questions 1–3 are resolved — Día = streak, UTC/Monday-start weeks, MCQ-only
   days count as active — so the heartbeat spike is the only remaining gate.)

### Key Decisions <!-- optional -->

- **Session tracking over a proxy.** "Minutes studied" gets a real write path
  (`POST /session`) rather than being approximated from `AnswerProgress` timestamps
  or video durations. The proxy was rejected: MCQ-answer times don't reflect time
  spent listening, and a learner can study a whole video without answering. The cost
  is new frontend instrumentation; the payoff is an honest number. (Chosen in
  discovery.)
- **Single-row `profile` table over static config.** Name/level live in a seeded DB
  row, not `config.py` constants, so they're editable (`PUT`) and so 023's Tweaks
  panel has a table to grow into. (Chosen in discovery.)
- **All-time comprehension over a rolling window.** Accuracy is `sum(is_correct) /
  count(*)` across all answers — stable and simple, matching the design's single
  `84 %`. A 7-day window was considered but rejected for v1 (empty on idle weeks,
  more volatile). (Chosen in discovery.)
- **`comprehension` is nullable.** No answers → `null` → `—`, never `0 %`. A real 0 %
  and "nothing answered yet" are different states and must render differently.
- **One aggregate endpoint** (`GET /api/profile`) returns identity + all three live
  KPIs together, so Inicio adds one fetch rather than fanning out.

### Testing Approach <!-- required -->

pytest on Postgres (the 029 fixture; per-test `TRUNCATE … RESTART IDENTITY CASCADE`).
Backend gets full coverage; the frontend heartbeat stays manual-smoke because the
IFrame player can't run headless (same posture as 015/021/028).

Backend test cases:

- **Profile defaults** — fresh DB exposes the seeded singleton (`name="Ana"`,
  `level="B2"`); `GET /api/profile` returns it.
- **`PUT /api/profile`** — updates name/level, persists, round-trips.
- **`POST /session`** — appends a `study_session`; rejects `seconds <= 0` and
  out-of-range values.
- **Week minutes** — sessions inside the current week sum into `week_minutes`;
  sessions from a prior week are excluded; empty → `0`.
- **Comprehension** — all-time accuracy from `AnswerProgress`; `null` when zero
  answered; correct rounding (e.g. 5/6 → `83`).
- **Streak** — consecutive active days up to today → N; a one-day gap resets;
  today-only → `1`; no activity → `0`; an MCQ-only day counts as active (OQ3
  default); session-only day counts as active.
- **Timezone boundary** — a session/answer just before vs just after the
  day/week boundary lands in the correct bucket (locks in the OQ2 decision).

Frontend manual smoke: play a video, confirm a `POST /session` fires on the
interval and on pause/unmount, confirm no accrual while paused, then visit Inicio
and confirm Esta semana / Racha / Comprensión render real values and `Frases
guardadas` is unchanged.
