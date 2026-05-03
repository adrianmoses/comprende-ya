import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/chunks")({ component: MisFrases });

function MisFrases() {
	return (
		<div className="placeholder">
			<h2>Mis frases</h2>
			<p>Saved-phrase library and speaking prompts land with feature 020.</p>
		</div>
	);
}
