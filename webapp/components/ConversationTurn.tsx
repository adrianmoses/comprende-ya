import type { VoiceResponse } from "@/lib/voice-protocol";

function MetricBadge({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex flex-col items-center rounded-lg bg-zinc-800 px-3 py-1.5">
      <span className="text-[10px] text-zinc-400">{label}</span>
      <span className="text-sm font-mono font-semibold text-white">
        {value.toFixed(0)}
        <span className="text-[10px] text-zinc-400">ms</span>
      </span>
    </div>
  );
}

interface ConversationTurnProps {
  response: VoiceResponse;
  showMetrics?: boolean;
}

export function ConversationTurn({
  response,
  showMetrics = true,
}: ConversationTurnProps) {
  return (
    <div className="space-y-2">
      {response.transcription && (
        <div className="rounded-lg bg-zinc-900 p-3">
          <p className="text-[10px] text-zinc-500 mb-0.5">You</p>
          <p className="text-sm text-zinc-200">{response.transcription}</p>
        </div>
      )}
      {response.response && (
        <div className="rounded-lg bg-zinc-900 p-3">
          <p className="text-[10px] text-zinc-500 mb-0.5">Profesor</p>
          <p className="text-sm text-zinc-200">{response.response}</p>
        </div>
      )}
      {showMetrics && (
        <div className="flex justify-center gap-2">
          <MetricBadge label="STT" value={response.data.stt_ms} />
          <MetricBadge label="LLM" value={response.data.llm_ms} />
          <MetricBadge label="TTS" value={response.data.tts_ms} />
          <MetricBadge label="Total" value={response.data.total_ms} />
        </div>
      )}
    </div>
  );
}
