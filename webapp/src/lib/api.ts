import type { VideoListResponse, VideoProgressResponse } from "./api-types";

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
