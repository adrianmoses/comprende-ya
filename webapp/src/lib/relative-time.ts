const MS_PER_DAY = 24 * 60 * 60 * 1000;

export function formatRelative(iso: string): string {
	const ms = Date.now() - Date.parse(iso);
	const days = Math.floor(ms / MS_PER_DAY);
	if (days < 1) return "hoy";
	if (days === 1) return "ayer";
	if (days < 7) return `hace ${days} días`;
	if (days < 14) return "hace 1 semana";
	if (days < 30) return `hace ${Math.floor(days / 7)} semanas`;
	if (days < 60) return "hace 1 mes";
	return `hace ${Math.floor(days / 30)} meses`;
}
