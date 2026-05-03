# webapp — Comprende Ya frontend

The desktop web frontend for ComprendeYa. TanStack Start (Vite + React 19 + Nitro + TanStack Router) on TypeScript strict, served as the shared shell that hosts every screen.

This is the spec-013 foundation: rail + topbar + theme tokens. Every route is a placeholder until its own feature spec lands (014 Inicio, 015 Escuchando, 016 Phrase Autopsy, 020 Mis frases, 023 Tweaks).

## Prerequisites

- Node 20+ (developed against 24.x)
- pnpm (enable via `corepack enable` if not installed)
- A running backend at `http://localhost:8000` for the API smoke call (see repo root `CLAUDE.md`)

## Run

```bash
pnpm install
pnpm dev          # dev server at http://localhost:3000
```

The dev port is pinned to 3000 because the FastAPI backend's CORS allowlist is `http://localhost:3000`.

## Build

```bash
pnpm build        # full Start build (client + server bundles)
pnpm typecheck    # tsc --noEmit
pnpm lint         # biome check (lint + format, CI-friendly)
pnpm format       # biome format --write
```

## Pointing at a non-default backend

Copy `.env.example` to `.env.local` and set `VITE_API_BASE_URL`:

```bash
cp .env.example .env.local
echo "VITE_API_BASE_URL=https://api.example.com" > .env.local
```

`.env.local` is gitignored. The API client at `src/lib/api.ts` reads this with a `http://localhost:8000` fallback.

## Where things live

- **Theme tokens.** `src/styles/tokens.css` — `:root` holds the light defaults, four `[data-theme="..."]` blocks (`dark`, `paper`, `sepia`, `cool`) override. The active theme is set by `data-theme` on `<html>` (default `dark`, see `src/routes/__root.tsx`). The user-facing switcher lands with feature 023.
- **Reset + shell.** `src/styles/reset.css`, `src/styles/shell.css`. All CSS is plain — no Tailwind, no CSS-in-JS.
- **Shell components.** `src/components/Rail.tsx`, `src/components/TopBar.tsx`, `src/components/icons.tsx`. Ported from `docs/artefacts/project/`.
- **API client.** `src/lib/api.ts` (typed `fetch` wrapper) + `src/lib/api-types.ts` (hand-mirrored from `src/models/schemas.py` and the actual route shapes).
- **Routes.** File-based under `src/routes/`. The root layout (rail + topbar + outlet) lives in `__root.tsx`.

## Adding a screen

1. Drop a new file in `src/routes/`. TanStack Router picks it up via the `tanstackStart` Vite plugin and regenerates `routeTree.gen.ts` on dev/build.
2. For static paths: `src/routes/myscreen.tsx` → `/myscreen`. For params: `src/routes/things.$id.tsx` → `/things/:id`. For nested: `src/routes/parent.child.tsx` → `/parent/child`.
3. Add a nav entry in `src/components/Rail.tsx` if it should appear in the sidebar.
4. Define the route handler:

```tsx
import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/myscreen")({ component: MyScreen });

function MyScreen() {
  return <div className="placeholder">…</div>;
}
```

## TanStack Router devtools

Floating bottom-right icon in dev. Inspect the route tree, params, search, loaders, etc. Mounted in `src/routes/__root.tsx`'s `RootDocument`; the `@tanstack/devtools-vite` plugin strips it from production builds automatically.
