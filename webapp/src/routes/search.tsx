import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useRouter } from "@tanstack/react-router";
import { useCallback, useEffect, useState } from "react";
import {
	checkVideosExist,
	getFlowStatus,
	processVideo,
	searchVideos,
} from "../lib/api";
import type { FlowStatusValue, SearchResult } from "../lib/api-types";

export const Route = createFileRoute("/search")({ component: Buscar });

function Buscar() {
	const [query, setQuery] = useState("");
	const [submitted, setSubmitted] = useState("");

	const searchQuery = useQuery({
		queryKey: ["search", submitted],
		queryFn: () => searchVideos(submitted),
		enabled: submitted.length > 0,
		retry: false, // surface a 503 immediately rather than retrying
	});

	const results = searchQuery.data?.results ?? [];
	const ids = results.map((r) => r.video_id);

	const existsQuery = useQuery({
		queryKey: ["exists", ids.join(",")],
		queryFn: () => checkVideosExist(ids),
		enabled: ids.length > 0,
	});
	const present = new Set(existsQuery.data?.present ?? []);

	return (
		<div className="page">
			<h1 className="page-h">Buscar</h1>
			<p className="page-sub">
				Encuentra un vídeo de YouTube y añádelo a tu biblioteca.
			</p>

			<form
				className="search-form"
				onSubmit={(e) => {
					e.preventDefault();
					setSubmitted(query.trim());
				}}
			>
				<input
					className="search-input"
					type="search"
					value={query}
					onChange={(e) => setQuery(e.target.value)}
					placeholder="p. ej. comprensión auditiva español"
					aria-label="Búsqueda de YouTube"
				/>
				<button type="submit" className="btn primary" disabled={!query.trim()}>
					Buscar
				</button>
			</form>

			{!submitted ? (
				<p className="search-state">Escribe algo y pulsa Buscar.</p>
			) : searchQuery.isPending ? (
				<p className="search-state">Buscando…</p>
			) : searchQuery.isError ? (
				<div className="search-state is-error">
					Búsqueda no disponible, intenta de nuevo.
				</div>
			) : results.length === 0 ? (
				<p className="search-state">Sin resultados para «{submitted}».</p>
			) : (
				<div className="lib-grid">
					{results.map((r) => (
						<ResultCard
							key={r.video_id}
							result={r}
							alreadyAdded={present.has(r.video_id)}
						/>
					))}
				</div>
			)}
		</div>
	);
}

function ResultCard({
	result,
	alreadyAdded,
}: {
	result: SearchResult;
	alreadyAdded: boolean;
}) {
	const router = useRouter();
	const queryClient = useQueryClient();
	const [flowRunId, setFlowRunId] = useState<string | null>(null);
	const [error, setError] = useState<string | null>(null);

	const goToListen = useCallback(
		() =>
			router.navigate({ to: "/listen/$id", params: { id: result.video_id } }),
		[router, result.video_id],
	);

	const processMutation = useMutation({
		mutationFn: () => processVideo(result.url),
		onSuccess: (resp) => {
			if (resp.status === "EXISTS") {
				goToListen();
			} else {
				setFlowRunId(resp.flow_run_id);
			}
		},
		onError: () => setError("No se pudo iniciar el procesamiento."),
	});

	const statusQuery = useQuery({
		queryKey: ["flow-status", flowRunId],
		queryFn: () => getFlowStatus(flowRunId as string),
		enabled: !!flowRunId,
		refetchInterval: (q) => {
			const s = q.state.data?.status;
			return s === "COMPLETED" || s === "FAILED" ? false : 2000;
		},
	});

	// React to terminal states: COMPLETED → refresh library + route in; FAILED →
	// stop polling and show the error inline (this is how an >1h video surfaces).
	const status = statusQuery.data?.status;
	const flowError = statusQuery.data?.error;
	useEffect(() => {
		if (status === "COMPLETED") {
			queryClient.invalidateQueries({ queryKey: ["videos"] });
			queryClient.invalidateQueries({ queryKey: ["videos-list"] });
			goToListen();
		} else if (status === "FAILED") {
			setFlowRunId(null);
			setError(flowError ?? "El procesamiento falló.");
		}
	}, [status, flowError, goToListen, queryClient]);

	const processing = !!flowRunId;

	return (
		<div className="card is-result">
			<div className="thumb">
				<img
					className="thumb-img"
					src={result.thumbnail}
					alt=""
					loading="lazy"
				/>
				<span className="thumb-dur">{result.duration_formatted}</span>
			</div>
			<div className="card-body">
				<div className="card-title">{result.title}</div>
				<div className="result-meta">
					{result.channel_title} · {result.view_count_formatted} vistas
				</div>

				{alreadyAdded ? (
					<Link
						to="/listen/$id"
						params={{ id: result.video_id }}
						className="result-added"
					>
						Ya añadido · Escuchar
					</Link>
				) : processing ? (
					<div className="result-processing">
						Procesando… {statusLabel(status)}
					</div>
				) : error ? (
					<div className="result-error">
						<span>{error}</span>
						<button
							type="button"
							className="btn"
							onClick={() => {
								setError(null);
								processMutation.mutate();
							}}
						>
							Reintentar
						</button>
					</div>
				) : (
					<button
						type="button"
						className="btn primary"
						disabled={processMutation.isPending}
						onClick={() => processMutation.mutate()}
					>
						{processMutation.isPending ? "Iniciando…" : "Procesar"}
					</button>
				)}
			</div>
		</div>
	);
}

function statusLabel(s: FlowStatusValue | undefined): string {
	if (s === "RUNNING") return "en curso";
	return "en cola";
}
