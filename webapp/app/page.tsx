"use client";

import { useVoiceAgent } from "@/hooks/useVoiceAgent";
import { useHealthCheck } from "@/hooks/useHealthCheck";

function MetricBadge({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex flex-col items-center rounded-lg bg-zinc-800 px-4 py-2">
      <span className="text-xs text-zinc-400">{label}</span>
      <span className="text-lg font-mono font-semibold text-white">
        {value.toFixed(0)}
        <span className="text-xs text-zinc-400">ms</span>
      </span>
    </div>
  );
}

export default function Home() {
  const health = useHealthCheck();
  const {
    recording,
    processing,
    lastResponse,
    error,
    startRecording,
    stopRecording,
  } = useVoiceAgent();

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-8 bg-zinc-950 p-8 text-white">
      <h1 className="text-3xl font-bold tracking-tight">Comprende Ya</h1>

      {/* Health indicator */}
      <div className="flex items-center gap-2 text-sm">
        <span
          className={`inline-block h-3 w-3 rounded-full ${
            health.connected ? "bg-green-500" : "bg-red-500"
          }`}
        />
        <span className="text-zinc-400">
          {health.connected
            ? `Voice agent connected${health.gpu ? ` — ${health.gpu}` : ""}`
            : "Voice agent offline"}
        </span>
      </div>

      {/* Record button */}
      <button
        onClick={recording ? stopRecording : startRecording}
        disabled={processing || !health.connected}
        className={`flex h-24 w-24 items-center justify-center rounded-full text-3xl transition-all
          ${
            recording
              ? "bg-red-600 shadow-lg shadow-red-600/30 animate-pulse"
              : processing
                ? "bg-zinc-700 cursor-not-allowed"
                : health.connected
                  ? "bg-blue-600 hover:bg-blue-500 shadow-lg shadow-blue-600/20 cursor-pointer"
                  : "bg-zinc-700 cursor-not-allowed"
          }`}
      >
        {processing ? "..." : recording ? "\u23F9" : "\u{1F3A4}"}
      </button>
      <p className="text-sm text-zinc-500">
        {processing
          ? "Processing..."
          : recording
            ? "Recording — click to stop"
            : "Click to start recording"}
      </p>

      {/* Error */}
      {error && (
        <p className="rounded-lg bg-red-900/50 px-4 py-2 text-sm text-red-300">
          {error}
        </p>
      )}

      {/* Transcription & response */}
      {lastResponse && (
        <div className="w-full max-w-md space-y-4">
          <div className="rounded-lg bg-zinc-900 p-4">
            <p className="text-xs text-zinc-500 mb-1">You said</p>
            <p className="text-zinc-200">{lastResponse.transcription}</p>
          </div>
          <div className="rounded-lg bg-zinc-900 p-4">
            <p className="text-xs text-zinc-500 mb-1">Agent replied</p>
            <p className="text-zinc-200">{lastResponse.response}</p>
          </div>

          {/* Metrics */}
          <div className="flex justify-center gap-3">
            <MetricBadge label="STT" value={lastResponse.data.stt_ms} />
            <MetricBadge label="LLM" value={lastResponse.data.llm_ms} />
            <MetricBadge label="TTS" value={lastResponse.data.tts_ms} />
            <MetricBadge label="Total" value={lastResponse.data.total_ms} />
          </div>
        </div>
      )}
    </main>
  );
}
