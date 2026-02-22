import type { Activity } from "@/lib/voice-protocol";

const TYPE_COLORS: Record<string, string> = {
  review: "bg-amber-600",
  conversation: "bg-blue-600",
  drill: "bg-purple-600",
  discrimination: "bg-rose-600",
};

interface ActivityCardProps {
  activity: Activity;
  index: number;
  total: number;
  elapsedSec?: number;
}

export function ActivityCard({
  activity,
  index,
  total,
  elapsedSec = 0,
}: ActivityCardProps) {
  const durationSec = activity.duration_estimate_min * 60;
  const progress = Math.min(1, elapsedSec / durationSec);
  const remainingSec = Math.max(0, durationSec - elapsedSec);
  const remainingMin = Math.floor(remainingSec / 60);
  const remainingSecMod = Math.floor(remainingSec % 60);
  const badgeColor = TYPE_COLORS[activity.activity_type] ?? "bg-zinc-600";

  return (
    <div className="w-full rounded-lg bg-zinc-900 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span
            className={`rounded px-2 py-0.5 text-xs font-semibold text-white ${badgeColor}`}
          >
            {activity.activity_type}
          </span>
          <span className="text-xs text-zinc-500">
            {index + 1}/{total}
          </span>
        </div>
        <span className="text-xs font-mono text-zinc-400">
          {remainingMin}:{remainingSecMod.toString().padStart(2, "0")}
        </span>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {activity.concept_names.map((name) => (
          <span
            key={name}
            className="rounded-full bg-zinc-800 px-2.5 py-0.5 text-xs text-zinc-300"
          >
            {name}
          </span>
        ))}
      </div>

      {/* Progress bar */}
      <div className="h-1 w-full rounded-full bg-zinc-800">
        <div
          className="h-1 rounded-full bg-blue-500 transition-all duration-1000"
          style={{ width: `${progress * 100}%` }}
        />
      </div>
    </div>
  );
}
