import { Link } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import type { Chunk } from "../lib/api-types";
import { formatRelative } from "../lib/relative-time";

const REC_STUB_MS = 3500;

type Props = { chunk: Chunk };

export function ChunkCard({ chunk }: Props) {
	const [promptIdx, setPromptIdx] = useState(0);
	const [isRecording, setIsRecording] = useState(false);
	const recTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
	const total = chunk.prompts.length;

	useEffect(() => {
		return () => {
			if (recTimeoutRef.current !== null) {
				clearTimeout(recTimeoutRef.current);
			}
		};
	}, []);

	const cyclePrompt = () =>
		setPromptIdx((i) => (total === 0 ? 0 : (i + 1) % total));

	const toggleRec = () => {
		if (isRecording) {
			if (recTimeoutRef.current !== null) clearTimeout(recTimeoutRef.current);
			recTimeoutRef.current = null;
			setIsRecording(false);
			return;
		}
		setIsRecording(true);
		recTimeoutRef.current = setTimeout(() => {
			recTimeoutRef.current = null;
			setIsRecording(false);
		}, REC_STUB_MS);
	};

	return (
		<div className="chunk">
			<div className="chunk-h">
				<h3 className="chunk-phrase">{chunk.phrase}</h3>
				<div className="mastery" title="Próximamente">
					<div className="mastery-dots">
						{[0, 1, 2, 3, 4].map((i) => (
							<span key={i} className="mastery-dot" />
						))}
					</div>
				</div>
			</div>
			<div className="chunk-source">
				<span>de</span>
				<Link
					to="/listen/$id"
					params={{ id: chunk.video_id }}
					search={{ t: chunk.start_time }}
					className="chunk-source-link"
				>
					{chunk.source_title}
				</Link>
				<span>·</span>
				<span>{formatRelative(chunk.created_at)}</span>
			</div>
			<div className="chunk-prompt">
				{total > 0 ? chunk.prompts[promptIdx] : "—"}
			</div>
			<div className="chunk-actions">
				<button
					type="button"
					className={isRecording ? "rec-btn is-recording" : "rec-btn"}
					onClick={toggleRec}
					aria-label="Grabar respuesta (próximamente)"
				>
					<span className="rec-dot" />
					{isRecording ? "Grabando…" : "Grabar respuesta"}
				</button>
				<button
					type="button"
					className="cycle-btn"
					onClick={cyclePrompt}
					disabled={total < 2}
				>
					Otro prompt →
				</button>
				<div style={{ flex: 1 }} />
				<span className="prompt-counter">
					{total === 0 ? "0/0" : `${promptIdx + 1}/${total}`}
				</span>
			</div>
		</div>
	);
}
