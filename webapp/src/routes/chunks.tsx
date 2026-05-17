import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import type { ReactNode } from "react";
import { useState } from "react";
import { ChunkCard } from "../components/ChunkCard";
import {
	type ChunksFilter,
	ChunksFilterRow,
} from "../components/ChunksFilterRow";
import { listChunks } from "../lib/api";
import type { Chunk } from "../lib/api-types";

export const Route = createFileRoute("/chunks")({ component: MisFrases });

const WEEK_MS = 7 * 24 * 60 * 60 * 1000;

function applyFilter(chunks: Array<Chunk>, filter: ChunksFilter): Array<Chunk> {
	if (filter === "all") return chunks;
	const cutoff = Date.now() - WEEK_MS;
	return chunks.filter((c) => Date.parse(c.created_at) >= cutoff);
}

function MisFrasesShell({ children }: { children: ReactNode }) {
	return (
		<div className="page">
			<h1 className="page-h">Tu biblioteca de frases</h1>
			{children}
		</div>
	);
}

function MisFrases() {
	const chunksQuery = useQuery({
		queryKey: ["chunks"],
		queryFn: listChunks,
	});
	const [filter, setFilter] = useState<ChunksFilter>("all");

	if (chunksQuery.isLoading) return <ChunksSkeleton />;
	if (chunksQuery.isError)
		return <ChunksErrorState onRetry={() => chunksQuery.refetch()} />;
	if (!chunksQuery.data?.length) return <ChunksEmptyState />;

	const filtered = applyFilter(chunksQuery.data, filter);

	return (
		<MisFrasesShell>
			<p className="page-sub">
				Cada frase venía de algo que escuchaste. Practícala en voz alta hasta
				que salga sin pensar — los prompts cambian para que no memorices la
				respuesta.
			</p>
			<ChunksFilterRow
				filter={filter}
				onFilter={setFilter}
				totalCount={chunksQuery.data.length}
			/>
			{filtered.length === 0 ? (
				<div className="filter-empty">Nada esta semana.</div>
			) : (
				<div className="chunks-grid">
					{filtered.map((c) => (
						<ChunkCard key={c.id} chunk={c} />
					))}
				</div>
			)}
		</MisFrasesShell>
	);
}

function ChunksSkeleton() {
	return (
		<MisFrasesShell>
			<div className="chunks-grid">
				{[0, 1, 2].map((i) => (
					<div key={i} className="chunk is-skeleton">
						<div className="chunk-h">
							<h3 className="chunk-phrase">Cargando…</h3>
						</div>
					</div>
				))}
			</div>
		</MisFrasesShell>
	);
}

function ChunksErrorState({ onRetry }: { onRetry: () => void }) {
	return (
		<MisFrasesShell>
			<div className="empty-state">
				<p>No pudimos cargar tus frases.</p>
				<button type="button" className="btn primary" onClick={onRetry}>
					Reintentar
				</button>
			</div>
		</MisFrasesShell>
	);
}

function ChunksEmptyState() {
	return (
		<MisFrasesShell>
			<div className="empty-state">
				<p>Aún no has guardado frases.</p>
				<p className="muted">
					Abre cualquier vídeo y toca <em>Guardar en biblioteca</em> en una
					autopsia.
				</p>
				<Link to="/" className="btn primary">
					Ir a Inicio
				</Link>
			</div>
		</MisFrasesShell>
	);
}
