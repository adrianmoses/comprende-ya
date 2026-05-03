import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/listen/$id")({ component: Escuchando });

function Escuchando() {
	const { id } = Route.useParams();
	return (
		<div className="placeholder">
			<h2>Escuchando — {id}</h2>
			<p>
				Player, transcript, MCQ rail and Phrase Autopsy panel land with features
				015 and 016.
			</p>
		</div>
	);
}
