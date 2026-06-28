export type VideoQuestion = {
	id: number;
	correct_answer: number;
	timestamp: number;
	answers: string;
	explanation: string;
};

export type VideoListItem = {
	id: number;
	video_id: string;
	title: string;
	duration: number;
	questions: Array<VideoQuestion>;
	created_at: string;
};

export type VideoListResponse = {
	videos: Array<VideoListItem>;
};

export type ProgressSummary = {
	answered: number;
	correct: number;
	incorrect: number;
};

export type ProgressRow = {
	question_id: number;
	user_answer: number;
	is_correct: boolean;
	answered_at: string;
};

export type VideoProgressResponse = {
	video_id: string;
	summary: ProgressSummary;
	progress: Array<ProgressRow>;
};

export type VideoDetailQuestion = {
	id: number;
	timestamp: number;
	question: string;
	answers: Array<string>;
	correct_answer: number;
	explanation: string | null;
};

export type VideoDetail = {
	id: number;
	video_id: string;
	url: string;
	title: string;
	duration: number;
	questions: Array<VideoDetailQuestion>;
	created_at: string;
};

export type TokenWord = {
	t: string;
	span?: number;
	start?: boolean;
};

export type TokenPunct = {
	p: string;
};

export type SegmentToken = TokenWord | TokenPunct;

export type TranscriptSegment = {
	segment_number: number;
	transcript: string;
	start_time: number;
	end_time: number;
	tokens: Array<SegmentToken> | null;
};

export type SaveProgressResponse = {
	question_id: number;
	user_answer: number;
	is_correct: boolean;
	answered_at: string;
};

export type Chunk = {
	id: number;
	video_id: string;
	source_title: string;
	phrase: string;
	start_time: number;
	prompts: Array<string>;
	has_recording: boolean;
	created_at: string;
};

export type Recording = {
	id: number;
	chunk_id: number;
	content_type: string;
	size_bytes: number;
	duration_seconds: number | null;
	created_at: string;
};

export type ChunkSaveRequest = {
	video_id: string;
	phrase: string;
	start_time: number;
};

export type ProfileResponse = {
	name: string;
	level: string;
	dia: number; // mirrors streak (item 022, OQ1)
	week_minutes: number;
	streak: number;
	comprehension: number | null; // null = no MCQs answered yet
};

export type ProfileUpdateRequest = {
	name?: string;
	level?: string;
};

export type SearchResult = {
	video_id: string; // YouTube id
	url: string;
	title: string;
	description: string;
	thumbnail: string;
	channel_title: string;
	published_at: string;
	duration: number; // seconds
	duration_formatted: string;
	view_count: number;
	view_count_formatted: string;
};

export type SearchResponse = { results: Array<SearchResult> };

export type ExistsResponse = { present: Array<string>; missing: Array<string> };

// POST /process-async returns one of two shapes, discriminated by `status` (031).
export type ProcessAsyncResponse =
	| {
			status: "EXISTS";
			message: string;
			result: { video_id: string; id: number };
	  }
	| { status: "PENDING"; message: string; flow_run_id: string };

export type FlowStatusValue = "PENDING" | "RUNNING" | "COMPLETED" | "FAILED";

export type FlowStatus = {
	flow_run_id: string;
	status: FlowStatusValue;
	url: string;
	youtube_video_id: string;
	video_id: number | null;
	error?: string;
};
