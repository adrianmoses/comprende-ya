export function formatDuration(seconds: number): string {
	const safe = Math.max(0, Math.floor(seconds));
	const m = Math.floor(safe / 60);
	const s = safe % 60;
	return `${m}:${s.toString().padStart(2, "0")}`;
}
