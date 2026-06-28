# Decision Record: Refresh + centralize Anthropic model IDs

| Field | Value |
|---|---|
| id | 026 |
| status | implemented |
| created | 2026-06-28 |
| spec | — (quick flow, no formal spec) |

---

## Context

The Anthropic model ID was hardcoded in six call sites, and four of them
carried a **transposed, invalid** string (`claude-4-sonnet-20250514`) that 404s
at the API — the root cause of video processing failing after the schema reset.
026 landed in two passes:

1. **In-place refresh (already merged in PR #16, branch `feat/022-…`).** All six
   call sites swapped to the valid current alias `claude-sonnet-4-6` to unblock
   processing and testing. Three `test_*_uses_locked_model` assertions that pinned
   the old literal were fixed in the same PR (caught by the full suite during the
   022 decision-record verification — the original swap was lint-checked but not
   suite-run).
2. **Centralization (this branch).** Removed the six-way duplication and split the
   call sites into two model tiers.

The roadmap's parenthetical named "Opus 4.7 / Sonnet 4.6 / Haiku 4.5"; current
most-capable is now Opus 4.8, but the generation tier stays on Sonnet 4.6 — the
existing behavior — and the cheap tier moves to Haiku 4.5.

## Decision

Two settings in `config.py`, each env-overridable, replace the six hardcoded
strings:

- `CLAUDE_MODEL` (`ANTHROPIC_MODEL`, default `claude-sonnet-4-6`) — the
  **generation** tier: MCQ generation (`questions.py`), phrase markers
  (`phrase_markers.py`), Phrase Autopsy (`phrase_autopsy.py`), chunk prompts
  (`chunk_prompts.py`).
- `CLAUDE_MODEL_CLASSIFY` (`ANTHROPIC_MODEL_CLASSIFY`, default `claude-haiku-4-5`)
  — the **classification** tier: both dialect classifiers
  (`dialect_classifier.py`, `classifier_repository.py`).

The three module-level `MODEL` constants now read `settings.CLAUDE_MODEL`; the two
classifiers and the two inline `questions.py` calls reference settings directly.
Documented in `.env.example` and `CLAUDE.md`.

---

## Alternatives Considered

### Model assignment strategy

**Option A — single centralized constant** (one model for all six sites)
- Pros: simplest; pure de-duplication, zero behavior change
- Cons: leaves the cheap, high-volume dialect classification on a mid-tier model

**Option B — two tiers** (generation = Sonnet 4.6, classification = Haiku 4.5)
- Pros: matches the roadmap's tiered hint; cuts cost on the two classifier calls
  (Haiku is ~⅓ the price) with no meaningful quality loss on a 6-way dialect label
- Cons: two constants instead of one; a second default to keep current

**Option C — three tiers incl. Opus** (Opus 4.8 for MCQs, Sonnet for other
generation, Haiku for classify)
- Pros: highest MCQ quality
- Cons: ~1.7× cost on the MCQ call for unproven benefit; more knobs

**Chosen:** B, per the user's call in the quick-flow scoping. Generation stays on
the already-validated Sonnet 4.6; classification drops to Haiku 4.5.

### Test assertion target

**Option A — assert the literal** (`== "claude-sonnet-4-6"`)
- Cons: re-breaks on every model change — exactly the brittleness that bit the
  in-place refresh

**Option B — assert each service module's `MODEL` constant**
- Pros: the test verifies "the call used the configured generation model" without
  re-encoding the literal; survives an env override or default bump

**Chosen:** B.

---

## Tradeoffs

- **A cheaper classifier could, in principle, classify worse.** Dialect
  classification is a coarse 6-way label over a transcript sample; Haiku 4.5 is
  expected to handle it fine, but this wasn't A/B-validated — it's a cost-led
  default, overridable via `ANTHROPIC_MODEL_CLASSIFY` if quality regresses.
- **Two constants, two defaults to maintain.** A future model refresh now touches
  `config.py` (and the `.env.example` / `CLAUDE.md` mentions) rather than six
  files — net simpler, but the defaults still need keeping-current.
- **No per-call override mechanism beyond the two tiers.** If a single task later
  needs its own model, it'd need a third setting; deemed premature now.

---

### Spec Divergence

No formal spec exists (quick flow). The implementation matches the scope agreed in
the scoping questions: centralize into settings, two tiers (Sonnet 4.6 generation /
Haiku 4.5 classification), env-overridable.

---

## Spec Gaps Exposed

- **The roadmap text is now slightly stale** — it reads "Opus 4.7 / Sonnet 4.6 /
  Haiku 4.5"; current most-capable is Opus 4.8. Not worth chasing in the table; the
  decision record carries the accurate state.
- No OVERVIEW/ARCHITECTURE gap surfaced; the model-ID staleness they flagged is now
  resolved and centralized.

---

## Test Evidence

The three service tests now assert against each module's `MODEL` constant
(robust to model changes); full suite green on Postgres.

```
$ uv run pytest -p no:warnings
...........................................................              [100%]
131 passed in 11.93s
```

```
$ grep -rn '"claude-sonnet-4-6"\|"claude-haiku-4-5"\|claude-4-sonnet' src/
src/config.py:21:    CLAUDE_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
src/config.py:22:    CLAUDE_MODEL_CLASSIFY = os.getenv("ANTHROPIC_MODEL_CLASSIFY", "claude-haiku-4-5")
# ^ the only model literals left in src/ are the two settings defaults
```

ruff check + format clean.
