export type VideoListItem = {
	id: number;
	video_id: string;
	title: string;
	duration: number;
	questions: number;
	created_at: string;
};

export type VideoListResponse = {
	videos: Array<VideoListItem>;
};
