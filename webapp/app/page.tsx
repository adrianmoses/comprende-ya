"use client";

import { useState } from "react";
import { useHealthCheck } from "@/hooks/useHealthCheck";
import { HealthIndicator } from "@/components/HealthIndicator";
import { PracticeView } from "@/components/PracticeView";
import { ProgressView } from "@/components/ProgressView";

type Tab = "practice" | "progress";

export default function Home() {
  const health = useHealthCheck();
  const [tab, setTab] = useState<Tab>("practice");

  return (
    <main className="flex min-h-screen flex-col items-center gap-6 bg-zinc-950 p-6 text-white">
      <h1 className="text-2xl font-bold tracking-tight">Comprende Ya</h1>

      <HealthIndicator status={health} />

      {/* Tabs */}
      <div className="flex gap-1 rounded-lg bg-zinc-900 p-1">
        <button
          onClick={() => setTab("practice")}
          className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
            tab === "practice"
              ? "bg-zinc-700 text-white"
              : "text-zinc-400 hover:text-zinc-200"
          }`}
        >
          Practice
        </button>
        <button
          onClick={() => setTab("progress")}
          className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
            tab === "progress"
              ? "bg-zinc-700 text-white"
              : "text-zinc-400 hover:text-zinc-200"
          }`}
        >
          Progress
        </button>
      </div>

      {/* Tab content */}
      {tab === "practice" ? (
        <PracticeView health={health} />
      ) : (
        <ProgressView />
      )}
    </main>
  );
}
