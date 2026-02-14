export const VOICE_AGENT_WS_URL =
  process.env.NEXT_PUBLIC_VOICE_AGENT_WS_URL ?? "ws://localhost:8765/ws/voice";

export const VOICE_AGENT_HEALTH_URL =
  process.env.NEXT_PUBLIC_VOICE_AGENT_HEALTH_URL ?? "http://localhost:8765/health";

export const SAMPLE_RATE = 16000;
export const NUM_CHANNELS = 1;
