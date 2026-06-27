import { useCallback, useEffect, useRef, useState } from "react";

const MAX_DURATION_MS = 30_000; // auto-stop: a phrase-length take, not a monologue

export type RecorderStatus = "idle" | "recording" | "denied" | "unsupported";

export type UseAudioRecorderArgs = {
	// Called whenever a recording finishes — manual stop OR max-duration auto-stop.
	onComplete: (blob: Blob, durationSeconds: number) => void;
};

export type UseAudioRecorderResult = {
	status: RecorderStatus;
	error: string | null;
	start: () => Promise<void>;
	stop: () => void;
};

// Wraps getUserMedia + MediaRecorder. All browser-API access lives inside the
// handlers below (never at module/render top level) so SSR never touches it.
// The recorded format is whatever MediaRecorder picks by default — the 021 spike
// confirmed Chrome's audio/webm;codecs=opus plays back as-stored, so we don't
// force a mimeType.
export function useAudioRecorder({
	onComplete,
}: UseAudioRecorderArgs): UseAudioRecorderResult {
	const [status, setStatus] = useState<RecorderStatus>("idle");
	const [error, setError] = useState<string | null>(null);

	const recorderRef = useRef<MediaRecorder | null>(null);
	const streamRef = useRef<MediaStream | null>(null);
	const chunksRef = useRef<Array<Blob>>([]);
	const startedAtRef = useRef<number>(0);
	const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
	const onCompleteRef = useRef(onComplete);
	onCompleteRef.current = onComplete;

	const cleanup = useCallback(() => {
		if (timeoutRef.current !== null) {
			clearTimeout(timeoutRef.current);
			timeoutRef.current = null;
		}
		streamRef.current?.getTracks().forEach((t) => {
			t.stop();
		});
		streamRef.current = null;
		recorderRef.current = null;
	}, []);

	const stop = useCallback(() => {
		// onstop (wired in start) assembles the blob and calls onComplete.
		recorderRef.current?.stop();
	}, []);

	const start = useCallback(async () => {
		setError(null);

		if (
			typeof navigator === "undefined" ||
			!navigator.mediaDevices?.getUserMedia ||
			typeof MediaRecorder === "undefined"
		) {
			setStatus("unsupported");
			setError("Tu navegador no permite grabar audio.");
			return;
		}

		let stream: MediaStream;
		try {
			stream = await navigator.mediaDevices.getUserMedia({ audio: true });
		} catch {
			setStatus("denied");
			setError("Permite el acceso al micrófono para grabar.");
			return;
		}

		streamRef.current = stream;
		chunksRef.current = [];
		const recorder = new MediaRecorder(stream);
		recorderRef.current = recorder;

		recorder.ondataavailable = (e) => {
			if (e.data.size > 0) chunksRef.current.push(e.data);
		};
		recorder.onstop = () => {
			const durationSeconds = (Date.now() - startedAtRef.current) / 1000;
			const blob = new Blob(chunksRef.current, {
				type: recorder.mimeType || "audio/webm",
			});
			cleanup();
			setStatus("idle");
			if (blob.size > 0) onCompleteRef.current(blob, durationSeconds);
		};

		startedAtRef.current = Date.now();
		recorder.start();
		setStatus("recording");
		timeoutRef.current = setTimeout(stop, MAX_DURATION_MS);
	}, [cleanup, stop]);

	// Stop tracks if the component unmounts mid-recording.
	useEffect(() => cleanup, [cleanup]);

	return { status, error, start, stop };
}
