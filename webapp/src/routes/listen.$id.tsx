import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { AutopsyPanel } from "../components/AutopsyPanel";
import { useStudyHeartbeat } from "../hooks/useStudyHeartbeat";
import { useYouTubePlayer } from "../hooks/useYouTubePlayer";
import {
	deleteChunk,
	explainPhrase,
	getVideo,
	getVideoProgress,
	getVideoSegments,
	listChunks,
	postSession,
	saveChunk,
	saveProgress,
} from "../lib/api";
import type {
	Chunk,
	ProgressRow,
	SegmentToken,
	TranscriptSegment,
	VideoDetailQuestion,
} from "../lib/api-types";
import type { AutopsyEntry } from "../lib/autopsy-types";
import { formatDuration } from "../lib/formatting";
import { normalizePhrase } from "../lib/normalize-phrase";

type ListenSearch = { t?: number };

export const Route = createFileRoute("/listen/$id")({
	component: Escuchando,
	validateSearch: (search: Record<string, unknown>): ListenSearch => {
		const raw = search.t;
		if (raw === undefined || raw === null || raw === "") return {};
		const t = Number(raw);
		return Number.isFinite(t) && t >= 0 ? { t } : {};
	},
});

const PLAYER_CONTAINER_ID = "yt-player";
const SPEED_CYCLE = [1, 0.85, 0.7, 1.25];
const CHOICE_LABELS = ["A", "B", "C", "D"];
const SPEAKER_LABEL = "Narrador/a";

type AutopsyState =
	| { state: "loading"; phrase: string; startTime: number }
	| { state: "error"; phrase: string; startTime: number }
	| { state: "loaded"; entry: AutopsyEntry };

function nextSpeed(current: number): number {
	const idx = SPEED_CYCLE.indexOf(current);
	return SPEED_CYCLE[(idx + 1) % SPEED_CYCLE.length] ?? 1;
}

function isNotFoundError(error: unknown): boolean {
	return error instanceof Error && error.message.startsWith("404");
}

function Escuchando() {
	const { id: youtubeId } = Route.useParams();
	const { t: deepLinkTime } = Route.useSearch();
	const queryClient = useQueryClient();
	const deepLinkConsumed = useRef(false);

	const videoQuery = useQuery({
		queryKey: ["video", youtubeId],
		queryFn: () => getVideo(youtubeId),
		retry: (failureCount, error) => !isNotFoundError(error) && failureCount < 3,
	});
	const segmentsQuery = useQuery({
		queryKey: ["video-segments", videoQuery.data?.id],
		queryFn: () => {
			if (!videoQuery.data) throw new Error("video not loaded");
			return getVideoSegments(videoQuery.data.id);
		},
		enabled: !!videoQuery.data,
	});
	const progressQuery = useQuery({
		queryKey: ["video-progress", youtubeId],
		queryFn: () => getVideoProgress(youtubeId),
	});

	const mutation = useMutation({
		mutationFn: ({
			questionId,
			userAnswer,
		}: {
			questionId: number;
			userAnswer: number;
		}) => saveProgress(youtubeId, questionId, userAnswer),
		onSuccess: () => {
			queryClient.invalidateQueries({
				queryKey: ["video-progress", youtubeId],
			});
		},
	});

	const chunksQuery = useQuery({
		queryKey: ["chunks"],
		queryFn: listChunks,
	});
	const saveChunkMutation = useMutation({
		mutationFn: saveChunk,
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["chunks"] });
		},
	});
	const deleteChunkMutation = useMutation({
		mutationFn: deleteChunk,
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["chunks"] });
		},
	});

	const player = useYouTubePlayer({
		containerId: PLAYER_CONTAINER_ID,
		videoId: youtubeId,
	});

	// Report listening time so Inicio's "Esta semana" KPI accrues (item 022).
	// Fire-and-forget; on success refresh the cached profile so a later Inicio
	// visit reflects it. The invalidate is best-effort — a failed beat just
	// drops that slice rather than surfacing an error mid-listening.
	useStudyHeartbeat(player.isPlaying, (seconds) => {
		postSession(seconds)
			.then(() => queryClient.invalidateQueries({ queryKey: ["profile"] }))
			.catch(() => {});
	});

	const [currentTime, setCurrentTime] = useState(0);
	const [pendingQuestionId, setPendingQuestionId] = useState<number | null>(
		null,
	);
	const [pendingAnswer, setPendingAnswer] = useState<number | null>(null);
	const [playbackRate, setPlaybackRate] = useState(1);
	const [autopsy, setAutopsy] = useState<AutopsyState | null>(null);

	useEffect(() => {
		if (!player.isPlaying) return;
		const interval = setInterval(() => {
			setCurrentTime(player.getCurrentTime());
		}, 250);
		return () => clearInterval(interval);
	}, [player.isPlaying, player.getCurrentTime]);

	useEffect(() => {
		if (deepLinkConsumed.current) return;
		if (deepLinkTime === undefined) return;
		if (!player.isReady) return;
		player.seekTo(deepLinkTime);
		player.play();
		setCurrentTime(deepLinkTime);
		deepLinkConsumed.current = true;
	}, [deepLinkTime, player.isReady, player.seekTo, player.play]);

	const questions = videoQuery.data?.questions ?? [];
	const progressRows = progressQuery.data?.progress ?? [];
	const progressByQuestionId = useMemo(() => {
		const m = new Map<number, ProgressRow>();
		for (const row of progressRows) m.set(row.question_id, row);
		return m;
	}, [progressRows]);

	useEffect(() => {
		if (pendingQuestionId !== null) return;
		if (!questions.length) return;
		const due = questions.find(
			(q) => currentTime >= q.timestamp && !progressByQuestionId.has(q.id),
		);
		if (due) {
			setPendingQuestionId(due.id);
			setPendingAnswer(null);
			setAutopsy(null);
			player.pause();
			player.seekTo(due.timestamp);
		}
	}, [
		currentTime,
		questions,
		progressByQuestionId,
		pendingQuestionId,
		player.pause,
		player.seekTo,
	]);

	const onSeek = (fraction: number) => {
		const duration = videoQuery.data?.duration ?? 0;
		const target = Math.max(0, Math.min(1, fraction)) * duration;
		setCurrentTime(target);
		player.seekTo(target);
	};

	const onSkip = (delta: number) => {
		const duration = videoQuery.data?.duration ?? 0;
		const target = Math.max(0, Math.min(duration, currentTime + delta));
		setCurrentTime(target);
		player.seekTo(target);
	};

	const onCycleSpeed = () => {
		const next = nextSpeed(playbackRate);
		setPlaybackRate(next);
		player.setPlaybackRate(next);
	};

	const onTogglePlay = () => {
		if (player.isPlaying) player.pause();
		else player.play();
	};

	const onAnswer = (questionId: number, choice: number) => {
		setPendingAnswer(choice);
		mutation.mutate({ questionId, userAnswer: choice });
	};

	const onContinue = () => {
		setPendingQuestionId(null);
		setPendingAnswer(null);
		player.play();
	};

	const requestAutopsy = (phrase: string, startTime: number) => {
		setAutopsy({ state: "loading", phrase, startTime });
		explainPhrase(youtubeId, phrase, startTime)
			.then((entry) => {
				setAutopsy({ state: "loaded", entry });
			})
			.catch(() => {
				setAutopsy({ state: "error", phrase, startTime });
			});
	};

	const onPickSpan = (phrase: string, startTime: number) => {
		requestAutopsy(phrase, startTime);
	};

	const onCloseAutopsy = () => {
		setAutopsy(null);
	};

	const savedChunksByPhrase = useMemo(() => {
		const map = new Map<string, Chunk>();
		for (const c of chunksQuery.data ?? []) {
			if (c.video_id === youtubeId) {
				map.set(normalizePhrase(c.phrase), c);
			}
		}
		return map;
	}, [chunksQuery.data, youtubeId]);

	const savedChunkFor = (phrase: string): Chunk | undefined =>
		savedChunksByPhrase.get(normalizePhrase(phrase));

	const onToggleSavedPhrase = (phrase: string, startTime: number) => {
		deleteChunkMutation.reset();
		saveChunkMutation.reset();
		const existing = savedChunkFor(phrase);
		if (existing) {
			deleteChunkMutation.mutate(existing.id);
		} else {
			saveChunkMutation.mutate({
				video_id: youtubeId,
				phrase,
				start_time: startTime,
			});
		}
	};

	const onReplayAutopsy = (startTime: number) => {
		setCurrentTime(startTime);
		player.seekTo(startTime);
		player.play();
	};

	if (videoQuery.isError && isNotFoundError(videoQuery.error)) {
		return <NotFound />;
	}
	if (videoQuery.isError) {
		return <ErrorState onRetry={() => videoQuery.refetch()} />;
	}

	const video = videoQuery.data;
	const segments = segmentsQuery.data ?? [];
	const duration = video?.duration ?? 0;
	const dataReady = !!video && !segmentsQuery.isPending;
	const currentSegmentNumber =
		segments.find(
			(s) => currentTime >= s.start_time && currentTime < s.end_time,
		)?.segment_number ?? null;
	const pendingQuestion = pendingQuestionId
		? questions.find((q) => q.id === pendingQuestionId)
		: null;

	const saveChunkPending =
		saveChunkMutation.isPending || deleteChunkMutation.isPending;
	const saveChunkError = saveChunkMutation.isError
		? "No se pudo guardar — reintenta."
		: deleteChunkMutation.isError
			? "No se pudo eliminar — reintenta."
			: null;

	return (
		<div className={`listen ${dataReady ? "" : "listen-skeleton"}`}>
			<div>
				<VideoFrame
					title={video?.title ?? "Cargando…"}
					isPlaying={player.isPlaying}
					onTogglePlay={onTogglePlay}
				/>
				<Scrubber
					currentTime={currentTime}
					duration={duration}
					questions={questions}
					onSeek={onSeek}
				/>
				<Transport
					playbackRate={playbackRate}
					onSkip={onSkip}
					onCycleSpeed={onCycleSpeed}
				/>
				{dataReady ? (
					<Transcript
						segments={segments}
						currentSegmentNumber={currentSegmentNumber}
						onPickSpan={onPickSpan}
					/>
				) : (
					<TranscriptPlaceholder />
				)}
			</div>

			<aside className="aside">
				{pendingQuestion ? (
					<QuestionPanel
						question={pendingQuestion}
						pendingAnswer={pendingAnswer}
						existingRow={progressByQuestionId.get(pendingQuestion.id) ?? null}
						onAnswer={(choice) => onAnswer(pendingQuestion.id, choice)}
						onContinue={onContinue}
					/>
				) : autopsy ? (
					autopsy.state === "loading" ? (
						<AutopsyPanel
							state="loading"
							phrase={autopsy.phrase}
							onClose={onCloseAutopsy}
						/>
					) : autopsy.state === "error" ? (
						<AutopsyPanel
							state="error"
							phrase={autopsy.phrase}
							onClose={onCloseAutopsy}
							onRetry={() => requestAutopsy(autopsy.phrase, autopsy.startTime)}
						/>
					) : (
						<AutopsyPanel
							state="loaded"
							entry={autopsy.entry}
							isSaved={!!savedChunkFor(autopsy.entry.phrase)}
							pending={saveChunkPending}
							error={saveChunkError}
							onClose={onCloseAutopsy}
							onSave={() =>
								onToggleSavedPhrase(
									autopsy.entry.phrase,
									autopsy.entry.start_time,
								)
							}
							onReplay={() => onReplayAutopsy(autopsy.entry.start_time)}
						/>
					)
				) : (
					<AsideHint />
				)}
				{dataReady && (
					<SessionPanel
						questions={questions}
						segments={segments}
						progressByQuestionId={progressByQuestionId}
					/>
				)}
			</aside>
		</div>
	);
}

function TranscriptPlaceholder() {
	return (
		<div className="transcript">
			<div className="transcript-h">
				<h3>Transcripción</h3>
			</div>
			<div className="segment" />
			<div className="segment" />
			<div className="segment" />
		</div>
	);
}

function VideoFrame({
	title,
	isPlaying,
	onTogglePlay,
}: {
	title: string;
	isPlaying: boolean;
	onTogglePlay: () => void;
}) {
	return (
		<div className="video-wrap">
			<div className="video-canvas">
				<div id={PLAYER_CONTAINER_ID} />
			</div>
			<button
				type="button"
				className={`play-btn ${isPlaying ? "is-playing" : ""}`}
				onClick={onTogglePlay}
				aria-label={isPlaying ? "Pausar" : "Reproducir"}
			>
				{isPlaying ? "❚❚" : "▶"}
			</button>
			<div className="video-overlay">
				<div>
					<div className="video-title">{title}</div>
					<div className="video-channel">—</div>
				</div>
			</div>
		</div>
	);
}

function Scrubber({
	currentTime,
	duration,
	questions,
	onSeek,
}: {
	currentTime: number;
	duration: number;
	questions: Array<VideoDetailQuestion>;
	onSeek: (fraction: number) => void;
}) {
	const handleClick = (e: React.MouseEvent<HTMLDivElement>) => {
		const rect = e.currentTarget.getBoundingClientRect();
		onSeek((e.clientX - rect.left) / rect.width);
	};
	const pct = duration > 0 ? (currentTime / duration) * 100 : 0;
	return (
		<div className="scrubber">
			<div className="scrubber-time">{formatDuration(currentTime)}</div>
			<div
				className="scrub-bar"
				onClick={handleClick}
				onKeyDown={(e) => {
					if (e.key === "Enter") onSeek(0.5);
				}}
				role="slider"
				aria-valuemin={0}
				aria-valuemax={duration}
				aria-valuenow={currentTime}
				tabIndex={0}
			>
				<div className="scrub-fill" style={{ width: `${pct}%` }} />
				{questions.map((q) => (
					<div
						key={q.id}
						className="scrub-mark"
						style={{
							left: duration > 0 ? `${(q.timestamp / duration) * 100}%` : "0%",
						}}
					/>
				))}
				<div className="scrub-thumb" style={{ left: `${pct}%` }} />
			</div>
			<div className="scrubber-time" style={{ textAlign: "right" }}>
				{formatDuration(duration)}
			</div>
		</div>
	);
}

function Transport({
	playbackRate,
	onSkip,
	onCycleSpeed,
}: {
	playbackRate: number;
	onSkip: (delta: number) => void;
	onCycleSpeed: () => void;
}) {
	return (
		<div className="transport">
			<button type="button" className="skip-btn" onClick={() => onSkip(-5)}>
				← 5s
			</button>
			<button type="button" className="skip-btn" onClick={() => onSkip(5)}>
				5s →
			</button>
			<button type="button" className="speed" onClick={onCycleSpeed}>
				{playbackRate}×
			</button>
			<div style={{ flex: 1 }} />
			<span className="legend">
				<span className="legend-mark" />
				Pregunta de comprensión
			</span>
		</div>
	);
}

type SpanTokenWithPosition = { token: SegmentToken; position: number };

type SpanGroup = {
	span: number;
	startPosition: number;
	tokens: Array<SpanTokenWithPosition>;
};

type RenderItem =
	| { kind: "token"; token: SegmentToken; position: number }
	| { kind: "span"; group: SpanGroup };

function buildRenderItems(tokens: Array<SegmentToken>): Array<RenderItem> {
	const items: Array<RenderItem> = [];
	let i = 0;
	while (i < tokens.length) {
		const tok = tokens[i];
		if (!tok) break;
		if ("t" in tok && typeof tok.span === "number") {
			const spanIdx = tok.span;
			const group: SpanGroup = {
				span: spanIdx,
				startPosition: i,
				tokens: [],
			};
			while (i < tokens.length) {
				const next = tokens[i];
				if (!next) break;
				if ("t" in next && next.span === spanIdx) {
					group.tokens.push({ token: next, position: i });
					i += 1;
				} else {
					break;
				}
			}
			items.push({ kind: "span", group });
		} else {
			items.push({ kind: "token", token: tok, position: i });
			i += 1;
		}
	}
	return items;
}

function spanPhrase(group: SpanGroup): string {
	return group.tokens
		.map(({ token }) => ("t" in token ? token.t : ""))
		.filter(Boolean)
		.join(" ");
}

function Transcript({
	segments,
	currentSegmentNumber,
	onPickSpan,
}: {
	segments: Array<TranscriptSegment>;
	currentSegmentNumber: number | null;
	onPickSpan: (phrase: string, startTime: number) => void;
}) {
	return (
		<div className="transcript">
			<div className="transcript-h">
				<h3>Transcripción</h3>
			</div>
			{segments.map((seg) => {
				const isCurrent = seg.segment_number === currentSegmentNumber;
				return (
					<div
						key={seg.segment_number}
						className={`segment ${isCurrent ? "is-current" : ""}`}
					>
						<div className="seg-speaker">
							<span>{SPEAKER_LABEL}</span>
							<span className="ts">{formatDuration(seg.start_time)}</span>
						</div>
						<div className="seg-text">
							<SegmentText
								segment={seg}
								onPickSpan={(phrase) => onPickSpan(phrase, seg.start_time)}
							/>
						</div>
					</div>
				);
			})}
		</div>
	);
}

function SegmentText({
	segment,
	onPickSpan,
}: {
	segment: TranscriptSegment;
	onPickSpan: (phrase: string) => void;
}) {
	if (!segment.tokens || segment.tokens.length === 0) {
		return <>{segment.transcript}</>;
	}

	const items = buildRenderItems(segment.tokens);
	return (
		<>
			{items.map((item) => {
				if (item.kind === "span") {
					const phrase = spanPhrase(item.group);
					return (
						<Fragment key={`span-${item.group.startPosition}`}>
							<button
								type="button"
								className="tx-span"
								onClick={() => onPickSpan(phrase)}
							>
								{item.group.tokens.map(({ token, position }, j) => (
									<Fragment key={`tok-${position}`}>
										{j > 0 ? " " : null}
										{"t" in token ? token.t : ""}
									</Fragment>
								))}
							</button>{" "}
						</Fragment>
					);
				}
				const tok = item.token;
				if ("p" in tok) {
					return <Fragment key={`p-${item.position}`}>{tok.p}</Fragment>;
				}
				return <Fragment key={`t-${item.position}`}>{tok.t} </Fragment>;
			})}
		</>
	);
}

function QuestionPanel({
	question,
	pendingAnswer,
	existingRow,
	onAnswer,
	onContinue,
}: {
	question: VideoDetailQuestion;
	pendingAnswer: number | null;
	existingRow: ProgressRow | null;
	onAnswer: (choice: number) => void;
	onContinue: () => void;
}) {
	const effectiveAnswer = pendingAnswer ?? existingRow?.user_answer ?? null;
	const answered = effectiveAnswer !== null;
	const isCorrect = answered && effectiveAnswer === question.correct_answer;
	return (
		<div className="panel">
			<div className="panel-h">
				<h4>Pregunta de comprensión</h4>
				<span className="panel-tag">después del segmento</span>
			</div>
			<div className="panel-body">
				<div className="q-meta">¿Lo captaste?</div>
				<p className="q-prompt">{question.question}</p>
				<div className="choices">
					{question.answers.map((text, idx) => {
						let cls = "choice";
						if (answered) {
							if (idx === question.correct_answer) cls += " is-correct";
							else if (idx === effectiveAnswer) cls += " is-wrong";
							else cls += " is-disabled";
						}
						return (
							<button
								key={text}
								type="button"
								className={cls}
								onClick={() => !answered && onAnswer(idx)}
								disabled={answered}
							>
								<span className="key">{CHOICE_LABELS[idx]}</span>
								<span>{text}</span>
							</button>
						);
					})}
				</div>
				{answered && (
					<>
						<div className="q-explain">
							{isCorrect ? "✓ Exacto. " : "No del todo. "}
							{question.explanation}
						</div>
						<div className="q-foot">
							<button
								type="button"
								className="btn-continue"
								onClick={onContinue}
							>
								Seguir →
							</button>
						</div>
					</>
				)}
			</div>
		</div>
	);
}

function AsideHint() {
	return (
		<div className="aside-empty">
			<strong>Sigue escuchando.</strong>
			<div style={{ marginTop: 6 }}>
				Aparecerá una pregunta de comprensión en cada marca naranja del
				temporizador.
			</div>
		</div>
	);
}

function SessionPanel({
	questions,
	segments,
	progressByQuestionId,
}: {
	questions: Array<VideoDetailQuestion>;
	segments: Array<TranscriptSegment>;
	progressByQuestionId: Map<number, ProgressRow>;
}) {
	const answeredCount = questions.filter((q) =>
		progressByQuestionId.has(q.id),
	).length;
	return (
		<div className="panel">
			<div className="panel-h">
				<h4>Sesión</h4>
				<span className="panel-tag">
					{answeredCount}/{questions.length} preguntas
				</span>
			</div>
			<div
				className="panel-body"
				style={{ display: "flex", flexDirection: "column", gap: 10 }}
			>
				{questions.map((q, i) => {
					const row = progressByQuestionId.get(q.id);
					const seg = segments.find(
						(s) => q.timestamp >= s.start_time && q.timestamp < s.end_time,
					);
					const appearance = seg
						? formatDuration(seg.end_time)
						: formatDuration(q.timestamp);
					let circleCls = "session-circle";
					let label = String(i + 1);
					if (row) {
						circleCls += row.is_correct ? " is-correct" : " is-wrong";
						label = row.is_correct ? "✓" : "×";
					}
					const rowCls = `session-row ${row ? "is-answered" : ""}`;
					return (
						<div key={q.id} className={rowCls}>
							<div className={circleCls}>{label}</div>
							<div className="session-text">
								{row ? "Respondida" : `Aparece a las ${appearance}`}
							</div>
						</div>
					);
				})}
			</div>
		</div>
	);
}

function ErrorState({ onRetry }: { onRetry: () => void }) {
	return (
		<div className="page">
			<div className="listen-error">
				<div>No pudimos cargar este episodio.</div>
				<button type="button" onClick={onRetry}>
					Reintentar
				</button>
			</div>
		</div>
	);
}

function NotFound() {
	return (
		<div className="page">
			<div className="listen-not-found">
				<div>Este episodio no existe en tu biblioteca.</div>
				<Link to="/">Volver a Inicio</Link>
			</div>
		</div>
	);
}
