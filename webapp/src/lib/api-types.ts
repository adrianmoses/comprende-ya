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
