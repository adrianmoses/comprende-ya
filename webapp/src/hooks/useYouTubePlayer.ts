import { useCallback, useEffect, useRef, useState } from "react";

const SCRIPT_SRC = "https://www.youtube.com/iframe_api";

function ensureYouTubeApi(onReady: () => void) {
	if (!window._ytApiReadyQueue) {
		window._ytApiReadyQueue = [];
	}
	if (window.YT?.Player) {
		onReady();
		return;
	}
	window._ytApiReadyQueue.push(onReady);
	if (!window.onYouTubeIframeAPIReady) {
		window.onYouTubeIframeAPIReady = () => {
			const queue = window._ytApiReadyQueue ?? [];
			window._ytApiReadyQueue = [];
			for (const cb of queue) cb();
		};
	}
	if (!document.querySelector(`script[src="${SCRIPT_SRC}"]`)) {
		const tag = document.createElement("script");
		tag.src = SCRIPT_SRC;
		tag.async = true;
		document.head.appendChild(tag);
	}
}

export type UseYouTubePlayerArgs = {
	containerId: string;
	videoId: string;
	onStateChange?: (state: number) => void;
};

export type UseYouTubePlayerResult = {
	isReady: boolean;
	isPlaying: boolean;
	play: () => void;
	pause: () => void;
	seekTo: (seconds: number) => void;
	setPlaybackRate: (rate: number) => void;
	getCurrentTime: () => number;
};

export function useYouTubePlayer({
	containerId,
	videoId,
	onStateChange,
}: UseYouTubePlayerArgs): UseYouTubePlayerResult {
	const [isReady, setIsReady] = useState(false);
	const [isPlaying, setIsPlaying] = useState(false);
	const playerRef = useRef<YT.Player | null>(null);
	const onStateChangeRef = useRef(onStateChange);
	onStateChangeRef.current = onStateChange;

	useEffect(() => {
		let cancelled = false;
		let createdPlayer: YT.Player | null = null;

		const create = () => {
			if (cancelled) return;
			const Player = window.YT?.Player;
			if (!Player) return;
			const container = document.getElementById(containerId);
			if (!container) return;
			createdPlayer = new Player(containerId, {
				videoId,
				playerVars: {
					controls: 0,
					modestbranding: 1,
					rel: 0,
					playsinline: 1,
				},
				events: {
					onReady: () => {
						if (cancelled) return;
						playerRef.current = createdPlayer;
						setIsReady(true);
					},
					onStateChange: (event: YT.OnStateChangeEvent) => {
						if (cancelled) return;
						const state = event.data;
						const PLAYING = window.YT?.PlayerState.PLAYING ?? 1;
						setIsPlaying(state === PLAYING);
						onStateChangeRef.current?.(state);
					},
				},
			});
		};

		ensureYouTubeApi(create);

		return () => {
			cancelled = true;
			try {
				createdPlayer?.destroy();
			} catch {
				// Tolerate destroy failures (e.g. during HMR before onReady fires).
			}
			playerRef.current = null;
			setIsReady(false);
			setIsPlaying(false);
		};
	}, [containerId, videoId]);

	const play = useCallback(() => {
		playerRef.current?.playVideo();
	}, []);
	const pause = useCallback(() => {
		playerRef.current?.pauseVideo();
	}, []);
	const seekTo = useCallback((seconds: number) => {
		playerRef.current?.seekTo(seconds, true);
	}, []);
	const setPlaybackRate = useCallback((rate: number) => {
		playerRef.current?.setPlaybackRate(rate);
	}, []);
	const getCurrentTime = useCallback(() => {
		return playerRef.current?.getCurrentTime() ?? 0;
	}, []);

	return {
		isReady,
		isPlaying,
		play,
		pause,
		seekTo,
		setPlaybackRate,
		getCurrentTime,
	};
}
