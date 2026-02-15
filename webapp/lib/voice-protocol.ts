export interface VoiceMetrics {
  stt_ms: number;
  llm_ms: number;
  tts_ms: number;
  total_ms: number;
}

export interface VoiceResponse {
  type: "metrics";
  data: VoiceMetrics;
  transcription: string;
  response: string;
}
