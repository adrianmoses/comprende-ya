export function formatDuration(seconds: number): string {
	const safe = Math.max(0, Math.floor(seconds));
	const m = Math.floor(safe / 60);
	const s = safe % 60;
	return `${m}:${s.toString().padStart(2, "0")}`;
}

// Human-readable weekly study minutes for the Inicio KPI: "42 min" / "1 h 12 min".
export function formatWeekMinutes(minutes: number): string {
	const safe = Math.max(0, Math.floor(minutes));
	if (safe < 60) return `${safe} min`;
	const h = Math.floor(safe / 60);
	const m = safe % 60;
	return m === 0 ? `${h} h` : `${h} h ${m} min`;
}
