import { useQueries, useQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { getVideoProgress, listVideos } from "../lib/api";
import type { VideoListItem, VideoProgressResponse } from "../lib/api-types";
import { formatDuration } from "../lib/formatting";

export const Route = createFileRoute("/")({ component: Inicio });

type ProgressInfo = { progress: number; lastAnswered: number | null };

function hashColor(youtubeId: string): string {
	const hue =
		Array.from(youtubeId).reduce((a, c) => a + c.charCodeAt(0), 0) % 360;
	return `oklch(0.78 0.06 ${hue})`;
}

function deriveProgress(
	video: VideoListItem,
	data: VideoProgressResponse | undefined,
): ProgressInfo {
	const total = video.questions.length;
	const answered = data?.summary.answered ?? 0;
	const progress = total === 0 ? 0 : Math.min(answered / total, 1);
	const lastAnswered = data?.progress.length
		? Math.max(...data.progress.map((r) => Date.parse(r.answered_at)))
		: null;
	return { progress, lastAnswered };
}

function Inicio() {
	const videosQuery = useQuery({
		queryKey: ["videos"],
		queryFn: listVideos,
	});
	const videos = videosQuery.data?.videos ?? [];

	const progressQueries = useQueries({
		queries: videos.map((v) => ({
			queryKey: ["video-progress", v.video_id],
			queryFn: () => getVideoProgress(v.video_id),
			enabled: !!videosQuery.data,
		})),
	});

	const progressByYoutubeId = new Map<string, ProgressInfo>();
	videos.forEach((v, i) => {
		progressByYoutubeId.set(
			v.video_id,
			deriveProgress(v, progressQueries[i]?.data),
		);
	});

	const allProgressSettled =
		videos.length === 0 || progressQueries.every((q) => !q.isPending);

	const continueListening = allProgressSettled
		? videos
				.filter((v) => {
					const p = progressByYoutubeId.get(v.video_id);
					return p && p.progress > 0 && p.progress < 1;
				})
				.sort((a, b) => {
					const la = progressByYoutubeId.get(a.video_id)?.lastAnswered ?? 0;
					const lb = progressByYoutubeId.get(b.video_id)?.lastAnswered ?? 0;
					return lb - la;
				})
				.slice(0, 3)
		: [];

	const hasContinue = continueListening.length > 0;

	return (
		<div className="page">
			<Greeting hasContinue={hasContinue} />
			<KpiGrid />

			{videosQuery.isPending ? (
				<>
					<h2 className="section-title">Tu biblioteca</h2>
					<Skeleton />
				</>
			) : videosQuery.isError ? (
				<>
					<h2 className="section-title">Tu biblioteca</h2>
					<ErrorState onRetry={() => videosQuery.refetch()} />
				</>
			) : videos.length === 0 ? (
				<>
					<h2 className="section-title">Tu biblioteca</h2>
					<EmptyState />
				</>
			) : (
				<>
					{hasContinue && (
						<>
							<h2 className="section-title">Continúa escuchando</h2>
							<div className="lib-grid">
								{continueListening.map((v) => (
									<Card
										key={v.video_id}
										video={v}
										progress={
											progressByYoutubeId.get(v.video_id)?.progress ?? 0
										}
									/>
								))}
							</div>
							<div style={{ height: 36 }} />
						</>
					)}
					<h2 className="section-title">Tu biblioteca</h2>
					<div className="lib-grid">
						{videos.map((v) => (
							<Card
								key={v.video_id}
								video={v}
								progress={progressByYoutubeId.get(v.video_id)?.progress ?? 0}
							/>
						))}
					</div>
				</>
			)}
		</div>
	);
}

function Greeting({ hasContinue }: { hasContinue: boolean }) {
	return (
		<>
			<h1 className="page-h">Buenos días, Ana.</h1>
			<p className="page-sub">
				{hasContinue
					? "Continúa donde lo dejaste o explora un episodio nuevo de tu biblioteca."
					: "Elige un episodio para empezar a escuchar."}
			</p>
		</>
	);
}

function KpiGrid() {
	return (
		<div className="kpis">
			<div className="kpi">
				<div className="kpi-label">Esta semana</div>
				<div className="kpi-val kpi-pending">—</div>
			</div>
			<div className="kpi">
				<div className="kpi-label">Frases guardadas</div>
				<div className="kpi-val">0</div>
			</div>
			<div className="kpi">
				<div className="kpi-label">Racha</div>
				<div className="kpi-val kpi-pending">—</div>
			</div>
			<div className="kpi">
				<div className="kpi-label">Comprensión</div>
				<div className="kpi-val kpi-pending">—</div>
			</div>
		</div>
	);
}

function Card({ video, progress }: { video: VideoListItem; progress: number }) {
	return (
		<Link to="/listen/$id" params={{ id: video.video_id }} className="card">
			<div className="thumb" style={{ background: hashColor(video.video_id) }}>
				<span className="thumb-dur">{formatDuration(video.duration)}</span>
				<div className="thumb-progress">
					<span style={{ width: `${progress * 100}%` }} />
				</div>
			</div>
			<div className="card-body">
				<div className="card-title">{video.title}</div>
			</div>
		</Link>
	);
}

function EmptyState() {
	return <div className="lib-empty">Aún no has procesado ningún episodio.</div>;
}

function ErrorState({ onRetry }: { onRetry: () => void }) {
	return (
		<div className="lib-error">
			<div>No pudimos cargar tu biblioteca.</div>
			<button type="button" onClick={onRetry}>
				Reintentar
			</button>
		</div>
	);
}

function Skeleton() {
	return (
		<div className="lib-grid">
			{[0, 1, 2].map((i) => (
				<div key={i} className="card is-skeleton">
					<div className="thumb" />
					<div className="card-body">
						<div className="card-title">Cargando…</div>
					</div>
				</div>
			))}
		</div>
	);
}
