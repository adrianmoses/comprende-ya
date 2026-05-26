import type {
	Chunk,
	ChunkSaveRequest,
	SaveProgressResponse,
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
	const response = await fetch(`${BASE_URL}${path}`, {
		headers: { "Content-Type": "application/json" },
		...init,
	});
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
