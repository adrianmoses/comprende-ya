# Decision: Frontend project setup & shared shell

| Field | Value |
|---|---|
| spec | [spec.md](./spec.md) |
| plan | `~/.claude/plans/let-s-create-a-plan-lazy-meerkat.md` |
| status | implemented |
| created | 2026-05-03 |

---

## What shipped

`webapp/` at the repo root, scaffolded with TanStack Start. Three placeholder routes (Inicio, Escuchando, Mis frases), the rail + topbar chrome ported from `docs/artefacts/project/`, the four-theme CSS-variable token system (`dark` active by default), a typed `fetch` wrapper hitting the FastAPI backend, Biome 2.4.5 for lint+format, TypeScript strict (`noUncheckedIndexedAccess` enabled). Dev server pinned to `:3000` to match the backend's CORS allowlist.

## Toolchain

| Choice | Landed | Rationale |
|---|---|---|
| Toolchain | **TanStack Start** | Spike confirmed clean scaffold via `pnpm dlx @tanstack/cli create … --framework React --toolchain biome --no-examples`. File-based type-safe routing, Nitro server, Vite, React 19, devtools all wired in one CLI. The fallback (plain Vite + TanStack Router) was not needed. |
| Package manager | **pnpm 10.29** | Already installed, scaffolder's default, no friction. |
| React | **19.2** | Scaffolder's default (spec said "React 18+"; 19 is current). |
| Lint/format | **Biome 2.4.5** | `--toolchain biome` flag set this up automatically. Recommended rule set, no overrides. Auto-fix handled the initial cleanup pass (mostly missing semicolons + CSS canonicalisation, e.g., `0.90` → `0.9`). After `biome migrate --write`, the repo is clean. ESLint+Prettier fallback was not needed. |
| CSS strategy | **Plain CSS, no Tailwind** | Tailwind v4 was forcibly installed by the scaffolder (the CLI's `--no-tailwind` flag is documented as "ignored"). Removed cleanly post-scaffold via `pnpm remove tailwindcss @tailwindcss/vite @tailwindcss/typography` plus dropping `tailwindcss()` from the Vite plugins array. The shipped `src/styles.css` only re-exports `tokens.css` + `reset.css` + `shell.css`. |
| API types | **Hand-mirrored** | `src/lib/api-types.ts` mirrors the *actual* `GET /api/videos/` route shape (wrapped `{ videos: [...] }`, not the `VideoResponse` Pydantic schema). Codegen from OpenAPI deferred. |

## Deviations from spec

1. **SSR is enabled by default** (spec §Non-Goals said "we ship as a client-rendered SPA"). TanStack Start in 2026 is opinionated toward SSR — the document shell (`<html>`/`<head>`/`<body>`) is a React component (`shellComponent: RootDocument`), not a static `index.html`. The decision to keep SSR is deliberate: it eliminates the FOUC concern entirely (the `data-theme="dark"` attribute is in the initial HTML response, not set client-side after hydration), it removes the inline-script workaround the spec sketched, and the Nitro server runs only as the dev/static-build serving layer — there are no server functions or RPC, so the SSR cost is shared layout work, nothing more. Future feature specs may opt in to server functions or `loader`s; this spec does not.
2. **No `index.html`.** Replaced by `<html lang="es" data-theme="dark">` JSX inside `RootDocument` in `src/routes/__root.tsx`. Google Fonts links go through `head: () => ({ links })` on `createRootRoute` instead of a static `<link>`.
3. **Vitest + Testing Library installed but unused.** Scaffolder added them as devDeps and a `test: vitest run` script. Spec called for no frontend tests in 013; we did not write any, and the harness sits idle until a future frontend-test-infrastructure spec.
4. **TanStack devtools wired by default.** Floating bottom-right panel in dev. The `@tanstack/devtools-vite` plugin strips it from production builds automatically (verified via `pnpm build` log: `[@tanstack/devtools-vite] Removed devtools code from: /src/routes/__root.tsx`).

None of the deviations expand into spec §Non-Goals beyond the SSR call, which is justified above.

## Spike findings

The spike phase took ~15 min, well under the spec's 1-hour budget.

1. **Spike 1 (scaffolding):** Clean. The current CLI is `pnpm dlx @tanstack/cli create` (replaces deprecated `create-tsrouter-app`). Default `--framework React` produces a Start app with file-based routing; the variant filename for `/listen/:id` is `listen.$id.tsx` (dot-delimited, not nested directory).
2. **Spike 2 (port + env):** `package.json`'s `dev` script already pins `--port 3000`; no Vite config edit needed. `import.meta.env.VITE_API_BASE_URL` works through `vite/client` types (already in `tsconfig.json`'s `types` array).
3. **Spike 3 (theme attribute):** Trivial. `<html data-theme="dark">` is a JSX attribute on the SSR-rendered document — no FOUC mitigation needed because the attribute is in the initial response.

## Final verification

- `pnpm lint` — clean (Biome 2.4.5).
- `pnpm typecheck` — clean (TypeScript 6, strict).
- `pnpm build` — clean (client + SSR bundles).
- Backend boot + frontend boot manually verified. SSR HTML for all three routes contains the rail (with correct `is-active` class on the matching nav link), topbar (with correct crumbs and ghost buttons), and placeholder content. CORS preflight from origin `http://localhost:3000` to `GET /api/videos/` returns 200; the backend's videos endpoint returns 3 stored videos.

## Open follow-ups (none blocking)

- The default `viewport` is `width=1280` (matches the design's fixed-width 1280px desktop). When mobile/responsive ever lands (out of scope), this changes.
- The rail's `Episodios` and `Progreso` items in the Biblioteca section are non-functional `<button>`s today; they'll wire to real routes when those screens land.
- `SAVED_PHRASE_COUNT` constant in `Rail.tsx` is hard-coded to `0`. Real value comes from feature 020 (Mis frases / chunk library) when there's state to read.
- The Tweaks panel (023) will switch the `data-theme` attribute at runtime; the four token sets are already in place.
