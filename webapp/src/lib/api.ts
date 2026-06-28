import type {
	Chunk,
	ChunkSaveRequest,
	ExistsResponse,
	FlowStatus,
	ProcessAsyncResponse,
	ProfileResponse,
	ProfileUpdateRequest,
	Recording,
	SaveProgressResponse,
	SearchResponse,
	TranscriptSegment,
	VideoDetail,
	VideoListResponse,
	VideoProgressResponse,
} from "./api-types";
import type { AutopsyEntry } from "./autopsy-types";

const BASE_URL = (
	import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"
).replace(/\/+$/, "");

async function api<T>(path: string, init?: RequestInit): Promise<T> {
	// FormData bodies must NOT carry a JSON content-type — the browser sets the
	// multipart boundary itself. Only default to JSON for non-FormData requests.
	const headers =
		init?.body instanceof FormData
			? init.headers
			: { "Content-Type": "application/json", ...init?.headers };
	const response = await fetch(`${BASE_URL}${path}`, { ...init, headers });
	if (!response.ok) {
		throw new Error(`${response.status} ${response.statusText}`);
	}
	if (response.status === 204) {
		return undefined as T;
	}
	return (await response.json()) as T;
}

export function listVideos(): Promise<VideoListResponse> {
	return api<VideoListResponse>("/api/videos/");
}

export function getVideoProgress(
	youtubeId: string,
): Promise<VideoProgressResponse> {
	return api<VideoProgressResponse>(
		`/api/videos/${encodeURIComponent(youtubeId)}/progress`,
	);
}

export function getVideo(youtubeId: string): Promise<VideoDetail> {
	return api<VideoDetail>(`/api/videos/${encodeURIComponent(youtubeId)}`);
}

export function getVideoSegments(
	dbId: number,
): Promise<Array<TranscriptSegment>> {
	return api<Array<TranscriptSegment>>(`/api/videos/${dbId}/segments`);
}

export function explainPhrase(
	youtubeId: string,
	phrase: string,
	startTime: number,
): Promise<AutopsyEntry> {
	return api<AutopsyEntry>(
		`/api/videos/${encodeURIComponent(youtubeId)}/autopsy/explain`,
		{
			method: "POST",
			body: JSON.stringify({ phrase, start_time: startTime }),
		},
	);
}

export function listChunks(): Promise<Array<Chunk>> {
	return api<Array<Chunk>>("/api/chunks");
}

export function saveChunk(body: ChunkSaveRequest): Promise<Chunk> {
	return api<Chunk>("/api/chunks", {
		method: "POST",
		body: JSON.stringify(body),
	});
}

export function deleteChunk(id: number): Promise<void> {
	return api<void>(`/api/chunks/${id}`, { method: "DELETE" });
}

export function uploadRecording(
	chunkId: number,
	blob: Blob,
	durationSeconds?: number,
): Promise<Recording> {
	const form = new FormData();
	form.append("file", blob, "grabacion.webm");
	if (durationSeconds != null) {
		form.append("duration_seconds", String(durationSeconds));
	}
	return api<Recording>(`/api/chunks/${chunkId}/recording`, {
		method: "POST",
		body: form,
	});
}

export function deleteRecording(chunkId: number): Promise<void> {
	return api<void>(`/api/chunks/${chunkId}/recording`, { method: "DELETE" });
}

// Direct URL for a native <audio> element. `version` busts the browser cache
// after a re-record (the stored URL is otherwise stable across overwrites).
export function getRecordingUrl(chunkId: number, version?: number): string {
	const suffix = version != null ? `?v=${version}` : "";
	return `${BASE_URL}/api/chunks/${chunkId}/recording${suffix}`;
}

// Buscar — YouTube search + add-to-library (031).
export function searchVideos(query: string): Promise<SearchResponse> {
	const params = new URLSearchParams({ query, max_results: "12" });
	return api<SearchResponse>(`/api/videos/search?${params}`);
}

// Which youtube_ids are already in the library — marks "Ya añadido" (027 endpoint).
export function checkVideosExist(ids: Array<string>): Promise<ExistsResponse> {
	return api<ExistsResponse>("/api/videos/exists", {
		method: "POST",
		body: JSON.stringify({ ids }),
	});
}

export function processVideo(url: string): Promise<ProcessAsyncResponse> {
	return api<ProcessAsyncResponse>("/api/videos/process-async", {
		method: "POST",
		body: JSON.stringify({ url }),
	});
}

export function getFlowStatus(flowRunId: string): Promise<FlowStatus> {
	return api<FlowStatus>(`/api/videos/status/${encodeURIComponent(flowRunId)}`);
}

export function getProfile(): Promise<ProfileResponse> {
	return api<ProfileResponse>("/api/profile");
}

// Reports a slice of listening time. Fire-and-forget from the Escuchando
// heartbeat; the backend appends a study_session row (item 022).
export function postSession(seconds: number): Promise<void> {
	return api<void>("/api/profile/session", {
		method: "POST",
		body: JSON.stringify({ seconds }),
	});
}

export function updateProfile(
	body: ProfileUpdateRequest,
): Promise<ProfileResponse> {
	return api<ProfileResponse>("/api/profile", {
		method: "PUT",
		body: JSON.stringify(body),
	});
}

export function saveProgress(
	youtubeId: string,
	questionId: number,
	userAnswer: number,
): Promise<SaveProgressResponse> {
	const params = new URLSearchParams({
		question_id: String(questionId),
		user_answer: String(userAnswer),
	});
	return api<SaveProgressResponse>(
		`/api/videos/${encodeURIComponent(youtubeId)}/progress?${params}`,
		{ method: "POST" },
	);
}
