import type { StudiesState } from "@/lib/voice-protocol";

const TREND_ICONS: Record<string, string> = {
  improving: "\u2191",
  declining: "\u2193",
  plateau: "\u2192",
};

const TREND_COLORS: Record<string, string> = {
  improving: "text-green-400",
  declining: "text-red-400",
  plateau: "text-zinc-400",
};

function masteryColor(m: number): string {
  if (m >= 0.8) return "bg-green-500";
  if (m >= 0.5) return "bg-blue-500";
  if (m >= 0.3) return "bg-amber-500";
  return "bg-red-500";
}

export function ConceptCard({ state }: { state: StudiesState }) {
  const pct = Math.round(state.projected_mastery * 100);
  const trendIcon = TREND_ICONS[state.trend] ?? "\u2192";
  const trendColor = TREND_COLORS[state.trend] ?? "text-zinc-400";

  return (
    <div className="rounded-lg bg-zinc-900 p-3 space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-sm text-zinc-200 truncate">
          {state.concept_id}
        </span>
        <div className="flex items-center gap-2">
          <span className={`text-sm font-medium ${trendColor}`}>
            {trendIcon}
          </span>
          <span className="text-xs text-zinc-400 font-mono">
            {state.practice_count}x
          </span>
        </div>
      </div>

      {/* Mastery bar */}
      <div className="h-2 w-full rounded-full bg-zinc-800">
        <div
          className={`h-2 rounded-full transition-all ${masteryColor(state.projected_mastery)}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="flex justify-between text-[10px] text-zinc-500">
        <span>{pct}% mastery</span>
        <span>
          {state.half_life_days.toFixed(1)}d half-life
        </span>
      </div>
    </div>
  );
}
