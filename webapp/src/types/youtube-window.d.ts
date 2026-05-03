/// <reference types="youtube" />

interface Window {
	YT?: { Player: typeof YT.Player; PlayerState: typeof YT.PlayerState };
	onYouTubeIframeAPIReady?: () => void;
	_ytApiReadyQueue?: Array<() => void>;
}
