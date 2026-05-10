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
