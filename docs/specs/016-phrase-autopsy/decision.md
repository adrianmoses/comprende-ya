# Decision Record: Phrase Autopsy side panel

| Field | Value |
|---|---|
| id | 016 |
| status | implemented |
| created | 2026-05-06 |
| spec | [spec.md](./spec.md) |

---

## Context

016 is the second slot of the Escuchando right rail. Before this, the rail only surfaced MCQs (015); the user could be quizzed on the language but couldn't *interrogate* it — the editorial pillar named in OVERVIEW.md (transcript MCQs, Phrase Autopsy, Chunk Library) was missing its middle leg.

Two roadmap items the panel naturally depends on are still `planned`: 017 (backend autopsy data + Claude generator) and 018 (token-level transcript with tappable "interesting" words). Rather than block 016 on either, the spec deliberately scoped this as a frontend-only deliverable backed by a TypeScript fixture, with a temporary "Frases destacadas" list-card as the trigger mechanism. The frontend therefore ships ready to consume real data the moment 017 lands, and the temporary trigger deletes cleanly when 018 lands.

One discovery during plan-phase exploration shaped the implementation: the webapp already has a partial `.btn` system in `webapp/src/styles/shell.css:206–235` (with `.ghost` and `.sm` modifiers, used by `TopBar.tsx`). The spec was drafted assuming no such system existed and proposed autopsy-scoped `.btn-save` / `.btn-replay` classes. The plan elected to extend `.btn` with `.primary` and `.accent` modifiers ported from the design's button rules and use the shared system instead — fragmenting into autopsy-only buttons would be churn now and re-litigation when 020 (Mis frases) needs the same pair.

Manual smoke through the listening flow confirmed the panel behaves as specified: panel layers collapse independently, MCQ becoming due dismisses the autopsy panel and surfaces the question, after `Seguir` the trigger card returns with saved-phrase state preserved within the session, videos without fixture entries fall through to the original `AsideHint`, and reload resets saved state honestly (no stub persistence).

## Decision

Built `AutopsyPanel` and `AutopsyTriggerCard` as React components consumed by the existing `routes/listen.$id.tsx`, fed by a TypeScript fixture at `webapp/src/data/autopsy-fixtures.ts` keyed by YouTube video id. The panel renders two collapsible layers (Gramática, Por qué suena natural) — the design's English "Significado natural" layer is permanently dropped per OVERVIEW.md §Non-Goals. The trigger card lists the fixture-known phrases and is tagged `temporal · ver 018` as a deletion breadcrumb. The save button toggles a session-local `Set<string>`; no persistence until 020. Buttons use the shared `.btn` system in `shell.css`, which was extended with `.primary` and `.accent` modifiers ported from `docs/artefacts/project/styles.css:189–201`.

Aside priority chain in the route is `pendingQuestion → autopsyEntry → autopsyEntries.length > 0 → AsideHint`, with `SessionPanel` always rendering below. The MCQ-due effect was extended with a single `setAutopsyTarget(null)` line so an incoming question dismisses an open autopsy panel.

---

## Alternatives Considered

### Trigger mechanism (spec Open Question §1)

**Option A — list affordance card in the rail** ("Frases destacadas")
- Pros: discoverable, removable in one place when 018 lands, sidesteps the missing token-level data entirely
- Cons: doesn't match the design's eventual UX (tappable transcript words)

**Option B — dev-only topbar button** that opens the first fixture phrase
- Pros: zero rail churn
- Cons: hidden from manual smoke, doesn't exercise the saved-state visual cycle, feels demo-y

**Option C — hard-code character ranges per segment in a frontend map**
- Pros: visually closer to the eventual 018 UX
- Cons: duplicates work that 018 will redo with token-aware rendering; throw-away

**Chosen: A.** Card sits between MCQ and AsideHint in the priority chain, deletes as one component, and surfaces the feature visibly during smoke. Tagged `temporal · ver 018` so the breadcrumb is unmissable in the running app.

### Button classes (deviation from spec §How.7)

**Option A — autopsy-scoped `.btn-save` / `.btn-replay`** (per spec)
- Pros: zero ripple beyond the autopsy stylesheet
- Cons: adds a third button vocabulary alongside the existing `.btn` and the one-off `.btn-continue` from 015; 020 will need the same primary/accent visuals and would have to re-litigate

**Option B — extend the existing `.btn` system with `.primary` and `.accent`**
- Pros: converges on a single button vocabulary; 020 inherits the same buttons; `.btn.accent` is exactly the design's saved-state filled-accent visual
- Cons: deviates from the spec; touches `shell.css` (a file outside the autopsy feature scope)

**Chosen: B.** The `.btn` system was discovered during plan-phase exploration; the spec's authoring assumed it didn't exist. Adding `.primary` / `.accent` as modifiers in the canonical place (`shell.css`) costs three small CSS rules and avoids a fragmenting precedent.

### Save action shape (spec Open Question §3)

**Option A — session-local `Set<string>`** (per spec)
- Pros: honest about what 016 ships; flips visual state with no API lie; one-line replacement when 020 wires `POST /api/chunks`
- Cons: state vanishes on reload — visible during smoke, but expected

**Option B — stub mutation that no-ops on the backend**
- Pros: closer to 020's wiring shape
- Cons: lies about persistence; would need to be unwound when 020 actually ships its endpoint

**Option C — drop the save button until 020**
- Pros: maximally honest
- Cons: 020 then has to design + ship the visual + the wiring; the visual is part of this feature's design

**Chosen: A.** Visual contract ships now; persistence is one mutation away when 020 lands.

### JSX shape for the autopsy entry lookup (deviation from spec §How.6)

**Option A — IIFE inline in the JSX** (per spec)
- Pros: minimal added surface area in the route
- Cons: not idiomatic in this repo — no other route uses an IIFE inside JSX; reads as noise

**Option B — compute `autopsyEntry` above JSX**
- Pros: matches how `pendingQuestion` is already computed at `listen.$id.tsx:171`; reads naturally
- Cons: one more local const

**Chosen: B.** Mirrors the existing pattern.

### Set initializer

**Option A — eager `useState(new Set())`**
- Pros: shorter
- Cons: creates a discarded Set on every render after the first

**Option B — lazy `useState<Set<string>>(() => new Set())`**
- Pros: matches the project's `useMemo`-builds-Map convention at `listen.$id.tsx:93`; allocates once
- Cons: marginally more verbose

**Chosen: B.** Project convention.

---

## Tradeoffs

The chosen approach optimises for **independent shippability** — the panel exists and works without 017 or 018. The cost is twofold:

1. **A frontend-side fixture that needs to stay in sync with whatever 017's eventual API response shape converges on.** The fixture lives in one file (`webapp/src/data/autopsy-fixtures.ts`) and the type comes from `webapp/src/lib/autopsy-types.ts`, so when 017 lands, 017 *should* design its response to match these types verbatim — making the swap a one-import-line change in the route and a deletion of the fixture file.
2. **A "Frases destacadas" affordance that is explicitly temporary.** It's tagged `temporal · ver 018` in the panel header, so the visual itself flags the debt. When 018 ships tappable transcript words, both the trigger card component and its CSS rules (`.autopsy-list*`) delete cleanly; the autopsy panel itself does not change.

Other tradeoffs accepted:

- **Save state resets on reload** (session-local). Honest about pre-020 state.
- **Aside priority gives MCQ precedence over an open autopsy panel.** Stacking both would eat vertical space and the user can re-open after `Seguir`.
- **No transcript-side highlighting of the autopsy target.** Tied to the missing token-level rendering from 018; landing this without 018 would require a throw-away char-range mapping (Option C above).

---

### Spec Divergence

| Spec Said | What Was Built | Reason |
|---|---|---|
| Custom `.btn-save` / `.btn-replay` classes (spec §How.7) | Reused `.btn` from `shell.css`, extended with `.primary` and `.accent` modifiers ported from `docs/artefacts/project/styles.css:189–201` | The existing `.btn` system was discovered during plan-phase exploration; using it converges the button vocabulary instead of fragmenting it. 020 inherits the same buttons. |
| IIFE inline in JSX for autopsy entry lookup (spec §How.6) | Computed `autopsyEntry` as a `const` above the JSX, mirroring the existing `pendingQuestion` computation at `listen.$id.tsx:171` | IIFEs in JSX are not used anywhere else in this repo; the const form matches the local convention. |

No other divergence. All acceptance criteria in §What were satisfied: panel header with phrase + register + close, two collapsible layers (Gramática, Por qué suena natural), no English layer, session-local save toggle, `Re-escuchar` seek + play, MCQ-priority dismissal, deferred transcript markers / tappable words clearly tagged, empty-state cleanly hidden, all copy Spanish, all quality gates green.

---

## Spec Gaps Exposed

- **The webapp already has a partial `.btn` system** in `shell.css:206–235`. The spec was drafted assuming no shared button rules existed, which led it to propose autopsy-scoped twin classes. Future specs that add visually-buttoned UI should check `shell.css` first; consider extracting a "design system note" in `ARCHITECTURE.md` listing the shared CSS primitives (`.btn`, `.panel*`, `.aside`, `.scrub-*`, etc.) so this isn't re-discovered each time.
- **Aside-stacking question for future panels.** If 020 (Mis frases) adds a fourth slot — saved-phrase confirmation toast — the priority chain grows another link. The current chain is already nested ternary three deep. A small `<AsideContent />` dispatcher component might pay off when adding the fourth case; not warranted yet.
- **Fixture-shape contract with 017.** The spec didn't mandate that 017's API response shape match `AutopsyEntry` verbatim, but the cheapest swap requires it. Worth calling out explicitly when 017's spec is drafted: "the entry shape returned per phrase MUST match `webapp/src/lib/autopsy-types.ts:AutopsyEntry`."
- **`Re-escuchar` UX.** Spec says the panel stays open during replay; smoke confirmed this is fine because the autopsy panel doesn't fight the player for attention. If a future user complains that the panel is in the way during replay, a small follow-up could close the panel on replay. Not warranted yet.

---

## Test Evidence

```
$ pnpm lint
> webapp@ lint /home/adrian/Desarrollador/comprende-ya/webapp
> biome check

Checked 26 files in 11ms. No fixes applied.

$ pnpm typecheck
> webapp@ typecheck /home/adrian/Desarrollador/comprende-ya/webapp
> tsc --noEmit

(no errors)

$ pnpm build
> webapp@ build /home/adrian/Desarrollador/comprende-ya/webapp
> vite build

vite v8.0.10 building client environment for production...
✓ 184 modules transformed.
dist/client/assets/styles-DYDuvUIT.css       17.66 kB │ gzip:   3.92 kB
dist/client/assets/listen._id-0n5MOtx7.js    16.21 kB │ gzip:   5.74 kB
dist/client/assets/index-DnXGWUDX.js        345.48 kB │ gzip: 108.36 kB
✓ built in 226ms

vite v8.0.10 building ssr environment for production...
✓ 115 modules transformed.
dist/server/assets/listen._id-C5DXQhQp.js   24.26 kB │ gzip:  6.65 kB
dist/server/server.js                      166.25 kB │ gzip: 41.17 kB
✓ built in 163ms
```

**SSR smoke** — `curl -sS http://localhost:3000/listen/m1DFpkNdcv0` returned HTTP 200 and the response body contained the trigger card pre-hydration:

```html
<div class="panel">
  <div class="panel-h">
    <h4>Frases destacadas</h4>
    <span class="panel-tag">temporal · ver 018</span>
  </div>
  <div class="autopsy-list">
    <button type="button" class="autopsy-list-row">
      <span class="autopsy-list-phrase">«a eso de las nueve»</span>
      <span class="autopsy-list-register">cotidiano · neutral</span>
    </button>
    <button type="button" class="autopsy-list-row">
      <span class="autopsy-list-phrase">«no me da igual»</span>
      <span class="autopsy-list-register">cotidiano · enfático</span>
    </button>
  </div>
</div>
```

Confirms the fixture import is SSR-safe (no top-level `window` / `document` access) and the trigger card renders server-side with both fixture phrases.

**Manual smoke** — user-driven, verified the listening flow end-to-end on `/listen/m1DFpkNdcv0`: trigger card appears, click opens the panel, layers collapse independently, save toggles colour, `Re-escuchar` seeks + plays, MCQ becoming due dismisses the panel and surfaces the question, after `Seguir` the trigger card returns with saved-phrase state preserved within the session.
