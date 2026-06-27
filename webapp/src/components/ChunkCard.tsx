import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useCallback, useState } from "react";
import { useAudioRecorder } from "../hooks/useAudioRecorder";
import { deleteRecording, getRecordingUrl, uploadRecording } from "../lib/api";
import type { Chunk } from "../lib/api-types";
import { formatRelative } from "../lib/relative-time";

type Props = { chunk: Chunk };

export function ChunkCard({ chunk }: Props) {
	const queryClient = useQueryClient();
	const [promptIdx, setPromptIdx] = useState(0);
	// Bumped on each successful upload so a re-record reloads the <audio> (the
	// stored URL is otherwise stable across overwrites and the browser caches it).
	const [recVersion, setRecVersion] = useState(0);
	const total = chunk.prompts.length;

	const uploadMutation = useMutation({
		mutationFn: ({ blob, duration }: { blob: Blob; duration: number }) =>
			uploadRecording(chunk.id, blob, duration),
		onSuccess: () => {
			setRecVersion((v) => v + 1);
			queryClient.invalidateQueries({ queryKey: ["chunks"] });
		},
	});

	const deleteMutation = useMutation({
		mutationFn: () => deleteRecording(chunk.id),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["chunks"] });
		},
	});

	const onComplete = useCallback(
		(blob: Blob, duration: number) => {
			deleteMutation.reset();
			uploadMutation.mutate({ blob, duration });
		},
		[deleteMutation, uploadMutation],
	);

	const recorder = useAudioRecorder({ onComplete });

	const cyclePrompt = () =>
		setPromptIdx((i) => (total === 0 ? 0 : (i + 1) % total));

	const isRecording = recorder.status === "recording";
	const isUploading = uploadMutation.isPending;

	const onRecClick = () => {
		if (isRecording) {
			recorder.stop();
		} else {
			uploadMutation.reset();
			recorder.start();
		}
	};

	const recLabel = isUploading
		? "Subiendo…"
		: isRecording
			? "Grabando…"
			: chunk.has_recording
				? "Regrabar"
				: "Grabar respuesta";

	const message = recorder.error
		? recorder.error
		: uploadMutation.isError
			? "No se pudo subir — reintenta."
			: deleteMutation.isError
				? "No se pudo borrar — reintenta."
				: null;

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
					onClick={onRecClick}
					disabled={isUploading}
					aria-label={isRecording ? "Parar grabación" : "Grabar respuesta"}
				>
					<span className="rec-dot" />
					{recLabel}
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
			{chunk.has_recording && (
				<div className="chunk-playback">
					{/* biome-ignore lint/a11y/useMediaCaption: personal voice memo, no transcript track */}
					<audio
						controls
						className="chunk-audio"
						src={getRecordingUrl(chunk.id, recVersion)}
					/>
					<button
						type="button"
						className="rec-delete"
						onClick={() => deleteMutation.mutate()}
						disabled={deleteMutation.isPending}
					>
						{deleteMutation.isPending ? "Borrando…" : "Borrar"}
					</button>
				</div>
			)}
			{message && <p className="rec-message">{message}</p>}
		</div>
	);
}
