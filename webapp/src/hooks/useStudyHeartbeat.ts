import { useEffect, useRef } from "react";

// Flush accrued listening time roughly every 30s of *playback* so Inicio's
// weekly-minutes KPI updates without waiting for the user to pause (item 022).
const FLUSH_INTERVAL_MS = 30_000;
const TICK_MS = 1_000;

/**
 * Accumulates wall-clock time only while `isPlaying` is true and reports it in
 * whole seconds via `onFlush`. Flushes on the interval, and on every pause /
 * unmount (the effect cleanup accrues the final slice). Because accrual is gated
 * on `isPlaying`, paused and closed-tab time is never counted, and a mid-play
 * seek keeps the same playing run — no double count.
 *
 * Wall-clock (not `getCurrentTime()`) is deliberate: it measures time-on-task,
 * which is what "minutes studied" means; playback-rate changes don't distort it.
 */
export function useStudyHeartbeat(
	isPlaying: boolean,
	onFlush: (seconds: number) => void,
) {
	const onFlushRef = useRef(onFlush);
	onFlushRef.current = onFlush;

	// Sub-second remainder carried between flushes, in ms.
	const accumRef = useRef(0);
	// Wall-clock ms at the last tick while playing; null when paused.
	const lastTickRef = useRef<number | null>(null);

	useEffect(() => {
		if (!isPlaying) return;

		const flush = () => {
			const seconds = Math.floor(accumRef.current / 1000);
			if (seconds > 0) {
				accumRef.current -= seconds * 1000; // keep the remainder
				onFlushRef.current(seconds);
			}
		};

		lastTickRef.current = Date.now();
		const interval = setInterval(() => {
			const now = Date.now();
			accumRef.current += now - (lastTickRef.current ?? now);
			lastTickRef.current = now;
			if (accumRef.current >= FLUSH_INTERVAL_MS) flush();
		}, TICK_MS);

		return () => {
			clearInterval(interval);
			// Accrue the slice since the last tick, then flush what's whole.
			const now = Date.now();
			accumRef.current += now - (lastTickRef.current ?? now);
			lastTickRef.current = null;
			flush();
		};
	}, [isPlaying]);
}
