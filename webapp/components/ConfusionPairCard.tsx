import type { ConfusionPair } from "@/lib/voice-protocol";

export function ConfusionPairCard({ pair }: { pair: ConfusionPair }) {
  return (
    <div className="flex items-center gap-3 rounded-lg bg-zinc-900 p-3">
      <span className="rounded-full bg-rose-900/50 px-2.5 py-0.5 text-xs text-rose-300">
        {pair.concept_a}
      </span>
      <span className="text-xs text-zinc-500">vs</span>
      <span className="rounded-full bg-rose-900/50 px-2.5 py-0.5 text-xs text-rose-300">
        {pair.concept_b}
      </span>
      <span className="ml-auto text-[10px] text-zinc-500">
        {pair.evidence_count} evidence
      </span>
    </div>
  );
}
