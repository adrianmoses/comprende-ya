export type ChunksFilter = "all" | "recent";

type Props = {
	filter: ChunksFilter;
	onFilter: (f: ChunksFilter) => void;
	totalCount: number;
};

export function ChunksFilterRow({ filter, onFilter, totalCount }: Props) {
	return (
		<div className="filter-row">
			<button
				type="button"
				className={`chip ${filter === "all" ? "is-on" : ""}`}
				onClick={() => onFilter("all")}
			>
				Todas · {totalCount}
			</button>
			<button
				type="button"
				className="chip is-disabled"
				title="Próximamente"
				aria-disabled="true"
			>
				Necesitan práctica
			</button>
			<button
				type="button"
				className={`chip ${filter === "recent" ? "is-on" : ""}`}
				onClick={() => onFilter("recent")}
			>
				Añadidas esta semana
			</button>
			<div style={{ flex: 1 }} />
			<button
				type="button"
				className="btn sm is-disabled"
				title="Próximamente"
				aria-disabled="true"
			>
				Empezar sesión de práctica
			</button>
		</div>
	);
}
