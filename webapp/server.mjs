// Production server entry (033 — deployment readiness).
//
// `vite build` emits dist/server/server.js, which exports a web-standard fetch
// handler (request → Response), not a self-listening HTTP server. srvx is
// TanStack Start's own server runtime; we feed the built handler to it so the
// app serves over Node in production.
//
// Honors PORT (default 3000) and HOST (default 0.0.0.0 so it's reachable from
// outside the container).
import { serve } from "srvx";
import entry from "./dist/server/server.js";

const port = Number(process.env.PORT) || 3000;
const hostname = process.env.HOST || "0.0.0.0";

serve({
	port,
	hostname,
	fetch: (request) => entry.fetch(request),
});

console.log(`webapp listening on http://${hostname}:${port}`);
