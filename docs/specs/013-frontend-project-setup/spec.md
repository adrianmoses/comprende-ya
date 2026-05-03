## Spec: Frontend project setup & shared shell

| Field | Value |
|---|---|
| id | 013 |
| status | approved |
| created | 2026-05-03 |

---

## Why

The repo is backend-only. Every capability the design bundle frames — Inicio's library + KPIs, Escuchando's transcript + scrubber + MCQ rail + Phrase Autopsy, Mis frases' chunk library — depends on a frontend existing first. Items 014–016, 020, and 023 all assume a shell to mount into. None of them can land without (a) a build/dev toolchain, (b) a routing skeleton between Inicio / Escuchando / Mis frases, (c) the rail + topbar chrome that wraps every screen, and (d) the four-theme token system the prototype already pins down.

This spec is that foundation. It produces a working app at `http://localhost:3000` that renders the rail and topbar, navigates between three placeholder routes, and applies the dark theme by default — and nothing more. The screens themselves are subsequent specs.

The toolchain choice — **TanStack Start** vs **Vite + React + Nitro wired by hand** — is the central decision this spec resolves. Both routes end at the same runtime surface (Vite dev server, Nitro for any server-side glue, React for the UI); TanStack Start pre-integrates them with type-safe file-based routing.

### Consumer Impact

- **Ana, the single B2 learner using the app.** She can open `localhost:3000`, see the rail with three nav items (Inicio · Escuchando ahora · Mis frases), and click between them without errors. No screen has real content yet — every route is a labeled placeholder. The visual chrome (typography, dark theme, accent color, rail dimensions) is final.
- **Future Claude Code agents implementing 014–016, 020, 023.** They get a project to mount features into rather than spending the first half of every feature spec re-deciding bundler / router / styling / API-client.
- **The FastAPI backend.** Already CORS-pinned to `http://localhost:3000`; this spec uses port 3000 unchanged so no backend config moves.

### Roadmap Fit

- **Unblocks:** 014 (Inicio), 015 (Escuchando), 016 (Phrase Autopsy panel — mounts inside Escuchando), 020 (Mis frases), 023 (Tweaks panel — wires into the theme tokens this spec lands).
- **Doesn't block:** any backend item (017, 018, 019, 021, 022, 024, 026). Backend continues in parallel; the frontend stubs the calls it needs but does not require new endpoints to ship 013.
- **Depends on:** nothing. The implemented backend (008 video CRUD, 012 flow-status persistence) is sufficient for the placeholder shell. Real screens will assert against specific endpoints in their own specs.

---

## What

### Acceptance Criteria

- [ ] `cd webapp && npm install && npm run dev` (or `pnpm`/`bun` equivalent — see Approach §package-manager) starts a dev server at `http://localhost:3000` on a fresh checkout. Hot reload works for `.tsx` edits.
- [ ] `npm run build` produces a production build with no type errors.
- [ ] Visiting `/` redirects to or renders the **Inicio** placeholder.
- [ ] Three routes work and update the URL: `/` (Inicio), `/listen/:id` (Escuchando, with a hard-coded id like `mercados` for now), `/chunks` (Mis frases). Browser back/forward navigates correctly.
- [ ] The **rail** (220px sticky left sidebar) renders on every route with: brand mark "C" + "Comprende *Ya*", three primary nav items (Inicio · Escuchando ahora · Mis frases) with the prototype's icons, two secondary nav items (Episodios, Progreso) under a "Biblioteca" section header, and a footer block with "Ana · B2 / Día 6 de la racha" hard-coded. Active item shows the active state from the prototype.
- [ ] The **topbar** renders on every route with: breadcrumbs (single crumb on home/chunks; "Inicio › Escuchando" on listen) and right-aligned ghost buttons for "Buscar episodios" and a settings cog. Buttons are visual-only — no behavior.
- [ ] The **dark theme** is applied by default. Theme tokens (`--paper`, `--ink-*`, `--accent`, `--accent-soft`, `--hair-*`, etc.) are defined as CSS custom properties at `:root` and the `dark` overrides are applied. The other three themes (`paper`, `sepia`, `cool`) are defined as token sets but not user-switchable yet — that's 023.
- [ ] **Fonts load:** Inter (UI), Instrument Serif (`<em>` in brand, hero numerals later), JetBrains Mono (counters in nav). No FOUT regression on hard reload.
- [ ] An **API client** module exists (`src/lib/api.ts` or similar) with a configurable base URL via `VITE_API_BASE_URL` (default `http://localhost:8000`). It exports a typed `getVideos()` function that hits `GET /api/videos/` and returns the `VideoResponse[]` shape — proves the wire works end-to-end. The placeholder Inicio route calls it on mount and logs to console (no UI yet).
- [ ] **TypeScript strict.** `tsconfig.json` has `"strict": true`; the build compiles cleanly.
- [ ] **Linter/formatter.** Either Biome (single tool, recommended) or ESLint + Prettier configured and runnable via `npm run lint` / `npm run format`. Decision recorded post-implementation.
- [ ] Frontend lives in `webapp/` at the repo root (mirrors the design bundle's `comprende-ya/project/` layout but renamed to match Python convention of one-word lowercase). `webapp/.gitignore` excludes `node_modules`, `dist`, `.output`.
- [ ] `webapp/README.md` documents: how to run, how to point at a non-default backend, where the theme tokens live, where to add a new screen.
- [ ] After implementation: `decision.md` records (a) toolchain landed (TanStack Start vs DIY), (b) package manager, (c) lint/format tool, (d) any framework friction found during the spike.

### Non-Goals

- **Real screen content.** Inicio's library + KPIs (014), Escuchando's player + transcript + MCQ rail (015), Phrase Autopsy (016), Mis frases' chunk library + speaking prompts (020), Tweaks panel UI (023) — all out of scope. Each route renders a single `<h2>` placeholder that names the screen, plus the API smoke-call on Inicio.
- **Authentication / user accounts.** No login, no session. Single-user, hard-coded "Ana" string in the rail footer.
- **State management library.** No Redux, no Zustand, no Jotai. Until a screen genuinely needs cross-tree state, we use TanStack Router's URL state and React's local `useState`. Add a store when a feature spec proves it's needed.
- **Server-side rendering.** TanStack Start *can* SSR; we ship as a client-rendered SPA. Nitro is present (it's TanStack Start's default server) but used only as a static-asset / dev server. SSR is a future tweak if it ever matters.
- **i18n framework.** UI strings are Spanish, hard-coded in JSX. The app is for a Spanish learner; English UI is not a goal. No `react-intl`, no `i18next`.
- **Frontend tests.** No Vitest, no Playwright in this spec. Item 025 (test infrastructure) is backend-only by design; a separate frontend test spec lands when there's enough surface to justify it. Acceptance is manual: open the dev server, click each rail item, watch the URL change and the topbar crumbs update.
- **Mobile / responsive.** Design is fixed-width 1280px desktop. CSS uses absolute pixel widths for the rail and panel grids; no breakpoints, no media queries beyond `prefers-color-scheme` if it falls out free.
- **Docker for the frontend.** Local dev only. Container packaging is its own future spec when there's a deploy target.
- **CORS / production base URL plumbing.** Backend stays pinned to `localhost:3000` for now. Externalising CORS is a backend concern (already flagged in OVERVIEW audit notes).
- **Re-skinning the prototype.** Visual output matches the design bundle's HTML/CSS prototype. No "improvements" to layout, color, or copy in this spec.

### Open Questions

1. **TanStack Start or DIY?** Recommendation: **TanStack Start.** Rationale in Approach §1; alternative documented for the record.
2. **Package manager.** `npm`, `pnpm`, or `bun`? Recommendation: **pnpm** — fast, disk-efficient, mainstream, and TanStack Start's own examples use it. `bun` is tempting but its Vite plugin compatibility is occasionally rough; not worth the risk for foundation work.
3. **Lint/format: Biome or ESLint+Prettier?** Recommendation: **Biome.** Single binary, single config, fast, strong defaults, type-aware in 2026. ESLint+Prettier is the safe-but-noisier choice if Biome misses any TanStack Router-specific rules. Resolved in `decision.md` post-implementation.
4. **CSS strategy.** Plain CSS files (matching the prototype directly), CSS Modules, Tailwind, or vanilla-extract? Recommendation: **plain CSS with CSS Modules for component-scoped styles**, plus a single `tokens.css` for the theme variables. The prototype already gives us a complete CSS file we can port near-verbatim; tossing it for Tailwind would be busy-work. CSS Modules give us collision-free class names without a build-time runtime.
5. **Where do TypeScript types for API responses come from?** Hand-written in `src/lib/api-types.ts` for now, mirroring `src/models/schemas.py`. Auto-generation from FastAPI's OpenAPI schema is a nice-to-have but its own tooling decision; defer until the schema starts diverging.

---

## How

### Approach

#### 1. Toolchain decision: TanStack Start

**Recommendation:** use TanStack Start.

| Concern | TanStack Start | DIY (Vite + React Router + Nitro by hand) |
|---|---|---|
| Vite | ✓ built-in | ✓ direct dep |
| React 18+ | ✓ | ✓ |
| Server runtime (Nitro) | ✓ wired in, dev + prod | requires manual `nitropack` setup, separate dev orchestration |
| Routing | ✓ TanStack Router, file-based, **fully type-safe params and search** | TanStack Router or React Router added by hand; type-safety needs codegen step or manual route trees |
| Server functions (RPC, future-proof for API proxy or BFF) | ✓ first-class | bolt on later |
| Onboarding cost | one CLI: `npx create-tsrouter-app@latest webapp --start` (or equivalent in 2026) | several days of integration glue |
| Risk | newer than React Router; smaller ecosystem of conventions | well-trodden but more code to maintain |

The wins are the type-safe router and the absence of integration glue. The risk is mostly upgrade churn, which is bounded — Start has been GA for a while by 2026-05-03 and the underlying parts (Vite, Nitro, TanStack Router) are individually stable. We do not depend on Start's SSR or server-functions yet, but having them sitting there means 016/020/021 don't need to relitigate the toolchain.

**Fallback (if Start spike hits a wall — see Confidence §validate):** drop to plain Vite + TanStack Router (still typed, still file-based) + skip Nitro entirely. We don't need a server today; a static SPA against the FastAPI backend is enough. The scope of this spec doesn't change — the rail, topbar, theme tokens, and routing skeleton all still ship. Only `decision.md` records which path landed.

#### 2. Project layout

```
webapp/
├── package.json
├── tsconfig.json
├── vite.config.ts          # (or app.config.ts for Start)
├── biome.json              # or .eslintrc + .prettierrc
├── index.html
├── public/
│   └── (favicon, fonts if self-hosted later)
├── src/
│   ├── routes/
│   │   ├── __root.tsx          # Rail + TopBar layout
│   │   ├── index.tsx           # Inicio placeholder
│   │   ├── listen.$id.tsx      # Escuchando placeholder
│   │   └── chunks.tsx          # Mis frases placeholder
│   ├── components/
│   │   ├── Rail.tsx
│   │   ├── TopBar.tsx
│   │   └── icons.tsx           # ported from prototype's components.jsx
│   ├── styles/
│   │   ├── tokens.css          # :root vars + theme overrides (4 themes)
│   │   ├── reset.css
│   │   └── shell.css           # rail/topbar layout (ported from styles.css)
│   ├── lib/
│   │   ├── api.ts              # fetch wrapper + getVideos()
│   │   └── api-types.ts        # hand-written mirrors of src/models/schemas.py
│   └── main.tsx                # app entry (or generated by Start)
├── README.md
└── .gitignore
```

The route file names match TanStack Router's file-based routing conventions (`__root` for the layout, `listen.$id` for `/listen/:id`).

#### 3. The rail and topbar

Port directly from `docs/artefacts/project/Comprende Ya.html` lines 192–273:

- **Rail.** 220px wide, sticky, full-height, `border-right: 1px solid var(--hair)`. Brand block at top, two nav sections (Estudio + Biblioteca), avatar + "Ana · B2 / Día 6 de la racha" footer. Click an item → call `useNavigate()` from TanStack Router. Active state computed from `useMatchRoute()`.
- **TopBar.** Sits inside `.main`, shows breadcrumbs derived from the current route, plus two ghost buttons (search, settings). Settings button opens nothing yet (future 023).
- **Icons.** The prototype defines `IconHome`, `IconPlay`, `IconChunks`, `IconLibrary`, `IconStats`, `IconSearch`, `IconSettings`, `IconBookmarkFilled` as inline SVG React components in `components.jsx`. Port verbatim into `src/components/icons.tsx`.

#### 4. Theme tokens

Move the prototype's CSS custom properties into `src/styles/tokens.css`. Apply themes by setting a `data-theme="dark|paper|sepia|cool"` attribute on `<html>` and writing one selector per theme:

```css
:root, [data-theme="paper"] { /* light defaults from styles.css :root */ }
[data-theme="dark"]  { --paper: #1c1914; --ink: oklch(0.96 0.010 85); /* ... */ }
[data-theme="sepia"] { /* ... */ }
[data-theme="cool"]  { /* ... */ }
```

Default attribute is set in `index.html`'s `<html data-theme="dark">` so there is no FOUC on first paint. The dynamic switching mechanism (the inline `useEffect` blob in the prototype) is **not** ported here — that's the Tweaks panel's job (023). The token sets exist; only the user-facing switch is deferred.

#### 5. API client

`src/lib/api.ts`:

```ts
const BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${BASE}${path}`, { headers: { "Content-Type": "application/json" }, ...init });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

export const getVideos = () => api<VideoResponse[]>("/api/videos/");
```

The Inicio placeholder route calls `getVideos()` in a `useEffect`, logs the result, and renders `<h2>Inicio</h2>`. That single call is the end-to-end smoke that proves CORS, base URL, and types all work. **Tanstack Query is not added in this spec** — the wrapper is bare `fetch` until a screen has a real loading/error/cache need. Adding Query later is mechanical.

#### 6. Dev server port

TanStack Start (and Vite) default to 5173. We override to 3000 in `vite.config.ts` / `app.config.ts` so it matches the backend's CORS allowlist. Single line of config.

#### 7. Linter / formatter

If Biome: `biome.json` with the recommended rule set, `npm run lint` → `biome check .`, `npm run format` → `biome format --write .`. If Biome+TanStack-Router rules disagree on something concrete, fall back to ESLint + Prettier with `eslint-plugin-react`, `eslint-plugin-react-hooks`, and `@typescript-eslint`. The fallback is heavier but well-known.

#### 8. Out-of-scope checks

The spec ships when a human can:

1. Start the backend (`uv run fastapi run src/main.py --host 0.0.0.0 --port 8000`).
2. Start the frontend (`pnpm dev` in `webapp/`).
3. Open `http://localhost:3000`, see the rail + topbar + Inicio placeholder, see videos data logged in DevTools console, click "Escuchando ahora" and "Mis frases" and see the URL change + topbar crumbs update + correct active state in the rail.

No automated check. This is honest about where we are: until item 025-equivalent for the frontend exists, manual smoke is the bar.

### Confidence

**Level:** Medium

**Rationale:**

- **High** on the rail/topbar/tokens port. The prototype is complete, vetted by the user during design, and translates 1:1 to TSX + CSS Modules. Mostly mechanical work.
- **High** on the API client smoke call. CORS is already configured for `localhost:3000`; `GET /api/videos/` exists and is well-typed.
- **Medium** on TanStack Start specifically. It's GA but its conventions move faster than React Router's. The spike below validates that the version we land on doesn't have a sharp edge that would cost more time than just running plain Vite + TanStack Router.
- **Medium** on the package manager / lint-format choices. They're reversible and shouldn't block, but pnpm + Biome together are slightly less battle-tested in monorepo-adjacent projects than `npm + ESLint + Prettier`. Either path works — the call is in `decision.md`.

**Validate before proceeding:**

1. **Spike: scaffold a TanStack Start app and run it.** `npx create-tsrouter-app@latest scratch --start` (or whichever the current CLI is at 2026-05-03), `pnpm dev`, confirm dev server runs and a single placeholder route renders. Confirm the file-based router picks up `routes/index.tsx` and `routes/listen.$id.tsx`. ~30 min. **If the scaffolding is broken or has a hard incompatibility with React 18+/Vite 5+, abandon Start and switch to plain Vite + TanStack Router.** Spec doesn't change; only Approach §1 collapses.
2. **Spike: confirm we can override the dev server port to 3000 and that `import.meta.env.VITE_*` env vars work the same way under Start as under plain Vite.** ~10 min.
3. **Spike: confirm `data-theme="dark"` set in `index.html` survives Start's HTML processing without being stripped or re-rendered after hydration.** ~10 min — relevant for FOUC. If Start mangles `index.html`, set the attribute via a tiny inline script before app mount.

Total spike budget: ~1 hour before committing the full implementation.

### Key Decisions

- **TanStack Start over DIY Vite + Nitro.** Less integration glue, type-safe routing, optional server functions for free. Fallback is plain Vite + TanStack Router if the spike pushes back.
- **TypeScript strict from day one.** Flipping it on later costs ten times what enabling it now does.
- **CSS Modules + plain CSS, not Tailwind.** Prototype is plain CSS; porting verbatim is faster than re-expressing in atomic classes. Theme tokens stay where the design left them.
- **No state management library.** URL state via the router + local `useState`. Add a store when a feature spec proves it's needed.
- **Hand-written API types, not codegen.** OpenAPI codegen is its own decision; the schema is small and stable enough that mirroring `schemas.py` by hand is cheaper for now.
- **No frontend tests in this spec.** Manual smoke is the bar; automated frontend testing is a separate, future spec.
- **Dev port 3000 to match backend CORS.** Single config line; saves a backend round-trip.

### Testing Approach

This spec ships without automated tests, consistent with item 025's explicit deferral of frontend tests.

Acceptance is mechanical and human-checked:

- **Build:** `pnpm build` exits 0; no TS errors.
- **Lint/format:** `pnpm lint` and `pnpm format --check` exit 0.
- **Dev server smoke:** `pnpm dev` starts on `:3000`; the three routes load; rail active state updates; breadcrumbs update; the API smoke call to `/api/videos/` succeeds in DevTools (or surfaces a clean error if the backend isn't running).
- **Theme:** dark theme is the default first paint with no FOUC. Manually flipping `<html data-theme="paper">` in DevTools swaps the palette correctly — proves the token sets are real, even though the user-facing switch is deferred to 023.

When 014 (Inicio) lands, it inherits this shell unchanged and adds its own acceptance criteria + tests as the test infra for the frontend matures.
