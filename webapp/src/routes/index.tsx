import { createFileRoute } from "@tanstack/react-router";
import { useEffect } from "react";
import { listVideos } from "../lib/api";

export const Route = createFileRoute("/")({ component: Inicio });

function Inicio() {
	useEffect(() => {
		listVideos()
			.then((data) => {
				// Smoke check — proves the wire to the FastAPI backend is live.
				// Real Inicio UI lands with feature 014.
				console.log("[Inicio] listVideos →", data);
			})
			.catch((err: unknown) => {
				console.error("[Inicio] listVideos failed:", err);
			});
	}, []);

	return (
		<div className="placeholder">
			<h2>Inicio</h2>
			<p>
				Library and KPI cards land with feature 014. Open DevTools to see the
				smoke call to <code>GET /api/videos/</code>.
			</p>
		</div>
	);
}
