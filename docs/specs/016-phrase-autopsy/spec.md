# Spec: Phrase Autopsy side panel

| Field | Value |
|---|---|
| id | 016 |
| status | approved |
| created | 2026-05-05 |

---

## Why

Phrase Autopsy is the *editorial* leg of the product. Comprehension MCQs (already shipping in 015) test whether Ana followed the gist; Phrase Autopsy is the moment she stops, taps something that *sounded* native but she couldn't parse, and gets a Spanish-internal breakdown of why it works that way. Per OVERVIEW.md, this is one of three pillars (transcript MCQs, Phrase Autopsy, Chunk Library). Without it, the right rail in Escuchando never does anything except surface MCQs — Ana never inspects the language; she just gets quizzed on it.

The design positions Autopsy as the answer to "I understood the words but I'd never say it that way." The panel "lifts" the tapped phrase out of the transcript into folded layers — *Gramática*, *Por qué suena natural* — that Ana can collapse independently like a folded note. The phrase stays highlighted in place so she doesn't lose context.

This is the **frontend panel only**. Real autopsy data (017) and real tappable trigger via token-level annotations (018) ship separately; this spec wires the panel against a frontend fixture and a temporary trigger mechanism. When 017 + 018 land, the data source and trigger swap in without restructuring the panel itself.

### Consumer Impact

- **Ana**, the single B2 learner. After 015, the right rail has only one job (MCQs). After 016, mid-segment she can pop open Autopsy, read the Gramática layer, see why "no me da igual" carries the dative `me`, and close the panel — the audio is still paused at her place, the phrase is still highlighted in the transcript. This is the first time the product lets her *interrogate* the language instead of being quizzed on it.
- **020 (Mis frases / Chunk Library)** depends on the save-phrase action. The panel here renders the `Guardar en biblioteca` button so 020 only has to wire the action; the visual + interaction state lives in 016.
- **017 / 018 (backend pieces).** When those land, the only delta on this screen is: (a) replace the fixture import with an API fetch, (b) replace the "Frases destacadas" list trigger with tappable transcript words. Panel internals don't move.

### Roadmap Fit

- **Depends on:** 015 (Escuchando — the panel slots into the existing `<aside>` between `QuestionPanel` and `AsideHint`).
- **Soft-depends on:** 017 (real autopsy data) and 018 (tappable transcript). Both are still `planned`. This spec explicitly *does not* block on them — it ships a fixture-backed panel with a list-based trigger so the visual + interaction work isn't gated.
- **Unblocks:** 020 (Mis frases) — the save button and the saved-state visual indicator on transcript words live here.
- **Doesn't block:** any backend item.

---

## What

### Acceptance Criteria

- [ ] On `/listen/$id`, when no MCQ is pending, the right rail offers a way to open the Autopsy panel for a phrase that has fixture data (see §How for the trigger mechanism — list-based until 018 lands).
- [ ] **Panel header.** Shows the phrase quoted in editorial-serif (`«{phrase}»`), the small register tag (`cotidiano · neutral` etc.), and a close (×) button that returns the rail to its previous state.
- [ ] **Layer 1 — Gramática.** Collapsible. Open by default. Renders a list of `{tag, text}` rows, each with a small mono-font tag chip and a Spanish-only explanation. Empty state: never empty in practice (fixture entries always carry ≥ 1 grammar row).
- [ ] **Layer 2 — Por qué suena natural.** Collapsible. Open by default. Renders the `natural_notes` array as a vertical stack of bulleted Spanish notes (`— {note}`).
- [ ] **No "Significado natural" layer.** The design's English-translation layer is dropped permanently per OVERVIEW.md §Non-Goals (no English glosses anywhere). The data shape is `{ register, grammar: [{tag, text}], natural_notes: string[] }` — no `natural`, no `literal`.
- [ ] **Save button.** Renders `Guardar en biblioteca` with an outlined bookmark icon. Toggling switches to `Guardada en biblioteca` with a filled bookmark and an accent-coloured button. State is **session-local only** (a `Set<string>` of saved phrases held in the screen's state) — no persistence, no API call. Real persistence lands in 020.
- [ ] **`Re-escuchar` button.** When clicked, seeks the YouTube player to the start of the segment that contains the phrase and resumes playback. The panel stays open.
- [ ] **Aside priority.** When the panel is open and an MCQ becomes due (player crossed a question's timestamp), the MCQ panel takes priority and the autopsy panel is dismissed. The user can re-open it after answering. (Phrase data is small, re-opening is free.)
- [ ] **Saved-phrase visual marker on the transcript** (when token-level data exists from 018) — *deferred to 018*. For this spec, no transcript words are marked.
- [ ] **Tappable transcript words** — *deferred to 018*. Trigger mechanism for this spec is the list-based affordance described in §How.
- [ ] **Empty state.** When there are no autopsy phrases for the current video (fixture has none), the trigger affordance hides cleanly — no broken empty list, no console errors.
- [ ] All copy is Spanish.
- [ ] `pnpm lint` / `pnpm typecheck` / `pnpm build` clean.

### Non-Goals

- **Real backend autopsy data (item 017).** Frontend reads from a TypeScript fixture: `webapp/src/data/autopsy-fixtures.ts`. The fixture has 2–3 entries for one of the seeded videos so manual smoke is real. When 017 lands, the API fetch replaces the fixture import.
- **Tappable transcript words (item 018).** No token-level rendering, no underlined phrases, no `<span class="word">` swap on the transcript. The temporary trigger is a "Frases destacadas" affordance described in §How.
- **Persistent save to chunk library (item 020).** Save toggle is session-local. No `POST /api/chunks`, no toast, no persistence across reload. The button just flips visual state.
- **`Significado natural` (English) layer.** Permanently dropped — see OVERVIEW.md §Non-Goals. Not a deferral.
- **Saved-phrase markers in the transcript** (`is-saved` / `is-active` styling on words). These rendering rules are tied to tappable words and ship with 018.
- **Per-token highlight of the autopsy target inside the transcript** (`is-active`). Same dependency — needs token rendering from 018.
- **Confidence score / quality score on autopsy entries.** The data shape doesn't carry this and the design doesn't surface it; if 017 adds it, a follow-up can light it up here.
- **Frontend tests.** Same deferral as 013/014/015 — manual smoke is the bar until a frontend-test-infra spec lands.
- **Re-running / regenerating autopsy entries.** Implied by 017 if Claude generation is on-demand. Not in scope here.

### Open Questions

1. **Trigger mechanism without 018.** The design's trigger is "tap an underlined word in the transcript." Without 018, we have no token-level data and no underlines. Three options:
   - **(a) List affordance in the right rail** — render a small "Frases destacadas" card in the rail (above the SessionPanel, replacing or augmenting `AsideHint`) that lists the fixture-known phrases for this video. Click a phrase → open the panel. **Recommendation: yes.** It's discoverable, it's removable in one place when 018 lands, and it sidesteps the token-rendering problem entirely.
   - **(b) Demo-only button on the topbar** — visible only in dev mode, opens the first fixture phrase. Too cute, hides the feature from manual smoke.
   - **(c) Hard-code which character ranges in which segments are tappable in a frontend map.** Same shape as 018 but in the frontend, throw-away. Rejected — duplicates work that 018 will redo with token-aware rendering.

2. **Data shape for the fixture.** Two reasonable shapes:
   - **(a) Keyed by video YouTube id**: `{ [youtubeId]: { [phrase]: AutopsyEntry } }`. Matches "this video has these phrases."
   - **(b) Keyed by phrase only**: `{ [phrase]: AutopsyEntry }`. Matches the design's `window.AUTOPSY` (phrase-globally-unique). Simpler.
   - **Recommendation: (a).** Phrases like *"no me da igual"* aren't unique across videos. Keying by video matches what the eventual API will return (`GET /api/videos/{id}/autopsy` → entries scoped to one video). Cheap to migrate.

3. **Save button when 020 is far off — keep, hide, or stub-toast?** Recommendation: **keep, session-local toggle.** It's the most honest demo — Ana can see how the saved state will look, but it doesn't lie about persisting. When 020 lands, the toggle wires into a real mutation and the local Set goes away.

4. **Re-escuchar — segment boundaries when we don't know the phrase's segment.** The fixture entry needs to carry `segment_number` (or a `start_time`) so `Re-escuchar` knows where to seek. Cheapest: each fixture entry includes an explicit `start_time: number` field. The eventual API entry will carry the same.

5. **Should the panel close itself if the player is paused for an MCQ that becomes due?** Recommendation: **yes** — see Acceptance Criteria. The MCQ is a hard interrupt; if the user wanted to keep the autopsy open while answering an MCQ, the rail would have to stack two panels and the screen runs out of room. Cleaner to dismiss + let her re-open after `Seguir`.

6. **Editorial serif for the phrase header.** Tokens already define `--font-ed: "Instrument Serif"` per 013. Reuse — don't add a new font weight.

---

## How

### Approach

#### 1. Files added

```
webapp/src/components/AutopsyPanel.tsx          # the panel component
webapp/src/components/AutopsyTriggerCard.tsx    # the temporary list-based trigger
webapp/src/data/autopsy-fixtures.ts             # frontend fixture data
webapp/src/lib/autopsy-types.ts                 # AutopsyEntry, AutopsyTarget
webapp/src/styles/autopsy.css                   # ported autopsy CSS
```

Files touched:

- `webapp/src/routes/listen.$id.tsx` — add `autopsyTarget` state, wire panel into the aside, render the trigger card when no MCQ is pending and there's fixture data for this video, dismiss panel when an MCQ becomes due.
- `webapp/src/styles.css` — `@import "./styles/autopsy.css";` after `escuchando.css`.

#### 2. Types

```ts
// webapp/src/lib/autopsy-types.ts
export type AutopsyGrammarRow = { tag: string; text: string };

export type AutopsyEntry = {
  phrase: string;
  start_time: number;          // seconds — for "Re-escuchar"
  register: string;            // e.g. "cotidiano · neutral"
  grammar: Array<AutopsyGrammarRow>;
  natural_notes: Array<string>;
};

export type AutopsyTarget = {
  phrase: string;
  segmentNumber: number | null; // null until 018; falls back to start_time
};
```

#### 3. Fixture

`webapp/src/data/autopsy-fixtures.ts` exports a single function:

```ts
import type { AutopsyEntry } from "../lib/autopsy-types";

const FIXTURES: Record<string, Record<string, AutopsyEntry>> = {
  "m1DFpkNdcv0": {
    "a eso de las nueve": {
      phrase: "a eso de las nueve",
      start_time: 12,
      register: "cotidiano · neutral",
      grammar: [
        { tag: "preposición", text: "«a» marca la hora puntual." },
        { tag: "demostrativo neutro", text: "«eso» se refiere de forma vaga a un punto en el tiempo." },
        { tag: "partitivo «de»", text: "introduce el referente: «de las nueve»." },
      ],
      natural_notes: [
        "Suena más natural que «a las nueve» cuando la hora es aproximada.",
        "Si dijeras «a las nueve en punto», el oyente esperaría exactitud.",
        "Muy común en habla cotidiana; en un parte de noticias casi nunca lo oirías.",
      ],
    },
    // 1–2 more entries...
  },
};

export function getAutopsyEntries(youtubeId: string): Array<AutopsyEntry> {
  const byPhrase = FIXTURES[youtubeId] ?? {};
  return Object.values(byPhrase);
}

export function getAutopsyEntry(youtubeId: string, phrase: string): AutopsyEntry | null {
  return FIXTURES[youtubeId]?.[phrase] ?? null;
}
```

The two phrases come straight from the design's `window.AUTOPSY` (Spanish-only fields). At least one seeded video gets fixture coverage — it doesn't have to be every video. Empty-list handling on the trigger card covers the rest.

#### 4. Panel component

`webapp/src/components/AutopsyPanel.tsx`:

```tsx
type Props = {
  entry: AutopsyEntry;
  isSaved: boolean;
  onClose: () => void;
  onSave: () => void;
  onReplay: () => void;
};

export function AutopsyPanel({ entry, isSaved, onClose, onSave, onReplay }: Props) {
  const [openLayers, setOpenLayers] = useState({ grammar: true, register: true });
  const toggle = (k: "grammar" | "register") =>
    setOpenLayers((s) => ({ ...s, [k]: !s[k] }));
  return (
    <div className="panel">
      <div className="panel-h">
        <h4>Phrase Autopsy</h4>
        <button type="button" className="panel-close" onClick={onClose} aria-label="Cerrar">
          ×
        </button>
      </div>
      <div className="panel-body autopsy-head">
        <h2 className="autopsy-phrase">«{entry.phrase}»</h2>
        <div className="autopsy-register">{entry.register}</div>
      </div>

      <Layer
        n={1}
        title="Gramática"
        open={openLayers.grammar}
        onToggle={() => toggle("grammar")}
      >
        {entry.grammar.map((g, i) => (
          <div key={i} className="gram-row">
            <div className="gram-tag">{g.tag}</div>
            <div>{g.text}</div>
          </div>
        ))}
      </Layer>

      <Layer
        n={2}
        title="Por qué suena natural"
        open={openLayers.register}
        onToggle={() => toggle("register")}
      >
        {entry.natural_notes.map((n, i) => (
          <div key={i} className="nat-row">— {n}</div>
        ))}
      </Layer>

      <div className="autopsy-foot">
        <button
          type="button"
          className={isSaved ? "btn-save is-saved" : "btn-save"}
          onClick={onSave}
        >
          {isSaved ? "Guardada en biblioteca" : "Guardar en biblioteca"}
        </button>
        <button type="button" className="btn-replay" onClick={onReplay}>
          Re-escuchar
        </button>
      </div>
    </div>
  );
}
```

`Layer` is a tiny local component for the collapsible folded-note rows — header with number badge + chevron, body slot, `is-open` class drives the chevron rotation.

#### 5. Trigger card

`webapp/src/components/AutopsyTriggerCard.tsx`:

```tsx
type Props = {
  entries: Array<AutopsyEntry>;
  savedPhrases: Set<string>;
  onPick: (entry: AutopsyEntry) => void;
};

export function AutopsyTriggerCard({ entries, savedPhrases, onPick }: Props) {
  if (!entries.length) return null;
  return (
    <div className="panel">
      <div className="panel-h">
        <h4>Frases destacadas</h4>
        <span className="panel-tag">temporal · ver 018</span>
      </div>
      <div className="panel-body autopsy-list">
        {entries.map((e) => (
          <button
            key={e.phrase}
            type="button"
            className={savedPhrases.has(e.phrase) ? "autopsy-list-row is-saved" : "autopsy-list-row"}
            onClick={() => onPick(e)}
          >
            <span className="autopsy-list-phrase">«{e.phrase}»</span>
            <span className="autopsy-list-register">{e.register}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
```

The `panel-tag` value `temporal · ver 018` is a deliberate breadcrumb for whoever picks up 018 — it makes the temporary nature of this affordance unmissable in the running app. Remove the whole component when 018 ships tappable transcript words.

#### 6. Wiring in `routes/listen.$id.tsx`

Add state:

```ts
const [autopsyTarget, setAutopsyTarget] = useState<AutopsyTarget | null>(null);
const [savedPhrases, setSavedPhrases] = useState<Set<string>>(() => new Set());
const autopsyEntries = useMemo(() => getAutopsyEntries(youtubeId), [youtubeId]);
```

Dismiss when an MCQ becomes due — extend the existing MCQ-due effect:

```ts
if (due) {
  setPendingQuestionId(due.id);
  setPendingAnswer(null);
  setAutopsyTarget(null);    // ← new
  player.pause();
  player.seekTo(due.timestamp);
}
```

Aside body — adjust the order to: pendingQuestion > autopsyPanel > triggerCard > AsideHint. Below, the SessionPanel still always renders.

```tsx
<aside className="aside">
  {pendingQuestion ? (
    <QuestionPanel … />
  ) : autopsyTarget ? (
    (() => {
      const entry = getAutopsyEntry(youtubeId, autopsyTarget.phrase);
      return entry ? (
        <AutopsyPanel
          entry={entry}
          isSaved={savedPhrases.has(entry.phrase)}
          onClose={() => setAutopsyTarget(null)}
          onSave={() =>
            setSavedPhrases((s) => {
              const next = new Set(s);
              if (next.has(entry.phrase)) next.delete(entry.phrase);
              else next.add(entry.phrase);
              return next;
            })
          }
          onReplay={() => {
            setCurrentTime(entry.start_time);
            player.seekTo(entry.start_time);
            player.play();
          }}
        />
      ) : null;
    })()
  ) : autopsyEntries.length > 0 ? (
    <AutopsyTriggerCard
      entries={autopsyEntries}
      savedPhrases={savedPhrases}
      onPick={(e) =>
        setAutopsyTarget({ phrase: e.phrase, segmentNumber: null })
      }
    />
  ) : (
    <AsideHint />
  )}
  {dataReady && <SessionPanel … />}
</aside>
```

The IIFE keeps the lookup local to the branch — small enough that splitting into a sub-component buys nothing.

#### 7. Styles

Port from `docs/artefacts/project/styles.css:675-770` into `webapp/src/styles/autopsy.css`:

- `.autopsy-phrase`, `.autopsy-register`, `.autopsy-head`
- `.layer`, `.layer-h`, `.layer-num`, `.layer-title`, `.layer-chev`, `.layer.is-open .layer-chev`, `.layer-body`
- `.gram-row`, `.gram-row:first-child`, `.gram-tag`
- `.nat-row`, `.nat-row:first-child`
- `.autopsy-foot`, `.btn-save`, `.btn-save.is-saved`, `.btn-replay`
- `.panel-close` (close × button shared shape)
- `.autopsy-list`, `.autopsy-list-row`, `.autopsy-list-row.is-saved`, `.autopsy-list-phrase`, `.autopsy-list-register`

Skip permanently (English layer): `.autopsy-natural` and the design's "Significado natural" layer rules.

The `.autopsy-list-*` classes are net-new — the design has no list affordance because its trigger is tappable transcript. Keep them in `autopsy.css` so they delete cleanly with the trigger card when 018 lands.

Add `@import "./styles/autopsy.css";` to `webapp/src/styles.css` after the `escuchando.css` import.

#### 8. Verification

Manual smoke against the existing seeded data:

1. Backend up, frontend up.
2. Open Inicio, click into the seeded video that has fixture entries (the spec ships fixtures for `m1DFpkNdcv0`).
3. Right rail shows "Frases destacadas" with the seeded phrases. Click one — panel opens, MCQ panel does not.
4. Toggle the Gramática and "Por qué suena natural" layers — both collapse independently, chevron rotates, body hides.
5. Click `Guardar en biblioteca` — button flips to `Guardada en biblioteca`, accent style, filled-state. Click again — flips back.
6. Click `Re-escuchar` — player seeks to `start_time` and resumes playback. Panel stays open.
7. Let playback run past a question's timestamp — autopsy panel dismisses, MCQ panel takes over. Answer the MCQ, click `Seguir`. Right rail returns to the trigger card. Click the same phrase — panel re-opens; saved state preserved within the session.
8. Open a video that has no fixture entries — right rail shows the original `AsideHint` (no trigger card). No console errors.
9. Reload the page — saved state resets (session-local). This is the expected behaviour pre-020.
10. `pnpm lint`, `pnpm typecheck`, `pnpm build` all clean.

### Confidence

**Level:** High

**Rationale:**

The panel is a styled-content component. No async, no SSR pitfalls (the consumer screen already SSR-renders fine in 015), no new dependencies. The risky decisions are scoping decisions — what to include vs. defer — and those are resolved in §Non-Goals and §Open Questions.

The one place where a mistake could hide: the aside priority logic when an MCQ becomes due while the panel is open. That's a single new line in the existing `useEffect` (`setAutopsyTarget(null)`) and gets caught immediately in the smoke step 7. Low risk.

The session-local saved-state choice is the kind of decision that often grows; if 020 ships within a sprint of this, the cost of replacing a `Set<string>` with a real mutation is trivial. If 020 slips, the visual remains honest because nothing claims persistence.

### Key Decisions

- **Frontend-only with a fixture, not blocked on 017.** Ships the panel as soon as it's ready. The fixture is one file, easy to delete when the API exists. The cost is a real-but-small fixture and keeping it in sync with 017's eventual response shape — manageable, especially since 017 will design its response *to fit this consumer*.
- **List-based trigger ("Frases destacadas") instead of tappable transcript.** Makes the feature exist independently of 018. Marked `temporal · ver 018` in the panel tag so the breadcrumb is unmissable. Deletes cleanly.
- **Save toggle is session-local, not stubbed against `POST /api/chunks`.** A stub would lie. Session-local is honest about what 016 actually delivers — the save *visual* — without pretending to be 020.
- **Two layers, not three.** The English "Significado natural" layer is permanently dropped, not deferred. Numbering goes Gramática (1) and Por qué suena natural (2).
- **Aside priority: MCQ wins over autopsy.** The MCQ is the hard interrupt; the autopsy is a side inquiry. Stacking both in the rail eats vertical space and the user can re-open the autopsy after `Seguir`.
- **`Re-escuchar` seeks to `entry.start_time` and plays.** Doesn't try to compute "the segment that contains the phrase" — the fixture carries `start_time` directly so the lookup is one field access. When 017 lands, the API entry carries the same field.
- **Editorial serif (`--font-ed`) on the phrase header.** Token already defined in 013; the design uses it for the same purpose.

### Testing Approach

Same as 013 / 014 / 015 — manual smoke is the bar; frontend automated test infra is its own future spec. After implementation:

- `pnpm lint`, `pnpm typecheck`, `pnpm build` all green.
- The ten manual-verification steps in §How.8.
- Decision record at `016-phrase-autopsy/decision.md` capturing: the actual aside-priority logic shape, any tweaks to the layer-collapse animation, the final fixture coverage (which video, how many phrases), any deviations from the ported CSS, and (if it surfaced) any rough edges in the trigger card that will make the 018 cutover non-trivial.
