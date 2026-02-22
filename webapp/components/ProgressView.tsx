"use client";

import { useEffect } from "react";
import { useLearnerProfile } from "@/hooks/useLearnerProfile";
import { useLearnerState } from "@/hooks/useLearnerState";
import { ConceptCard } from "./ConceptCard";
import { ConfusionPairCard } from "./ConfusionPairCard";

function SummaryCard({
  label,
  count,
  color,
}: {
  label: string;
  count: number;
  color: string;
}) {
  return (
    <div className="flex flex-col items-center rounded-lg bg-zinc-900 px-4 py-3">
      <span className={`text-2xl font-bold ${color}`}>{count}</span>
      <span className="text-[10px] text-zinc-400">{label}</span>
    </div>
  );
}

export function ProgressView() {
  const { profile, loading: profileLoading } = useLearnerProfile();
  const { states, confusions, contexts, loading: stateLoading, fetchAll } =
    useLearnerState();

  // Fetch full state on mount
  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  if (profileLoading && !profile) {
    return (
      <p className="text-sm text-zinc-500 text-center">Loading profile...</p>
    );
  }

  if (!profile) {
    return (
      <p className="text-sm text-zinc-500 text-center">
        No learner data yet. Complete a session to see progress.
      </p>
    );
  }

  return (
    <div className="w-full max-w-lg space-y-6">
      {/* Summary cards */}
      <div className="grid grid-cols-4 gap-2">
        <SummaryCard
          label="Mastered"
          count={profile.mastered?.length ?? 0}
          color="text-green-400"
        />
        <SummaryCard
          label="Progressing"
          count={profile.progressing?.length ?? 0}
          color="text-blue-400"
        />
        <SummaryCard
          label="Decaying"
          count={profile.decaying?.length ?? 0}
          color="text-amber-400"
        />
        <SummaryCard
          label="Unseen"
          count={profile.unseen?.length ?? 0}
          color="text-zinc-400"
        />
      </div>

      <p className="text-[10px] text-zinc-500 text-center">
        {profile.total_evidence_count ?? 0} total evidence events
      </p>

      {/* Concept grid */}
      {states.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold text-zinc-400 mb-2 uppercase tracking-wider">
            Concepts
          </h3>
          <div className="grid grid-cols-1 gap-2">
            {[...states]
              .sort((a, b) => b.projected_mastery - a.projected_mastery)
              .map((s) => (
                <ConceptCard key={s.concept_id} state={s} />
              ))}
          </div>
        </div>
      )}

      {/* Confusion pairs */}
      {confusions.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold text-zinc-400 mb-2 uppercase tracking-wider">
            Confusion Pairs
          </h3>
          <div className="space-y-2">
            {confusions.map((p, i) => (
              <ConfusionPairCard key={i} pair={p} />
            ))}
          </div>
        </div>
      )}

      {/* Effective contexts */}
      {contexts.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold text-zinc-400 mb-2 uppercase tracking-wider">
            Effective Contexts
          </h3>
          <div className="space-y-1.5">
            {contexts.map((c, i) => (
              <div
                key={i}
                className="flex items-center gap-3 rounded-lg bg-zinc-900 p-3"
              >
                <span className="rounded-full bg-blue-900/50 px-2.5 py-0.5 text-xs text-blue-300">
                  {c.context_id}
                </span>
                {c.concept_id && (
                  <span className="text-xs text-zinc-500">{c.concept_id}</span>
                )}
                <span className="ml-auto text-xs font-mono text-zinc-300">
                  {(c.effectiveness * 100).toFixed(0)}%
                </span>
                <span className="text-[10px] text-zinc-500">
                  ({c.sample_count})
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Refresh */}
      <button
        onClick={fetchAll}
        disabled={stateLoading}
        className="mx-auto block text-xs text-zinc-500 hover:text-zinc-300 transition-colors disabled:opacity-50"
      >
        {stateLoading ? "Refreshing..." : "Refresh data"}
      </button>
    </div>
  );
}
