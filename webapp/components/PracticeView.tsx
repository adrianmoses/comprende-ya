"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useVoiceAgent } from "@/hooks/useVoiceAgent";
import { useSession, type SessionMode } from "@/hooks/useSession";
import type { HealthStatus } from "@/hooks/useHealthCheck";
import type { VoiceResponse } from "@/lib/voice-protocol";
import { ActivityCard } from "./ActivityCard";
import { ConversationTurn } from "./ConversationTurn";

interface PracticeViewProps {
  health: HealthStatus;
}

export function PracticeView({ health }: PracticeViewProps) {
  const { session, loading, error: sessionError, startSession, endSession, handleServerMessage } =
    useSession();

  const [conversation, setConversation] = useState<VoiceResponse[]>([]);
  const [activityElapsed, setActivityElapsed] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval>>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const onServerMessage = useCallback(
    (msg: Parameters<typeof handleServerMessage>[0]) => {
      handleServerMessage(msg);
      if (msg.type === "metrics") {
        setConversation((prev) => [...prev, msg as VoiceResponse]);
      }
      if (msg.type === "activity_change") {
        setActivityElapsed(0);
      }
    },
    [handleServerMessage]
  );

  const voice = useVoiceAgent({ onServerMessage });

  // Activity timer
  useEffect(() => {
    if (session.active && session.currentActivity) {
      timerRef.current = setInterval(() => {
        setActivityElapsed((s) => s + 1);
      }, 1000);
      return () => {
        if (timerRef.current) clearInterval(timerRef.current);
      };
    }
    if (timerRef.current) clearInterval(timerRef.current);
  }, [session.active, session.currentActivity]);

  // Auto-scroll conversation
  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [conversation]);

  const handleStart = async (mode: SessionMode) => {
    setConversation([]);
    setActivityElapsed(0);
    const plan = await startSession(mode);
    if (plan !== null) {
      voice.connectWs();
    }
  };

  const handleEnd = async () => {
    voice.disconnectWs();
    await endSession();
  };

  // Pre-session: mode selection
  if (!session.active && !session.ended) {
    return (
      <div className="flex flex-col items-center gap-6">
        <p className="text-zinc-400 text-sm">Choose a practice mode</p>
        <div className="flex gap-3">
          <button
            onClick={() => handleStart("structured")}
            disabled={!health.connected || loading}
            className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-500 disabled:bg-zinc-700 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? "Planning..." : "Structured Session"}
          </button>
          <button
            onClick={() => handleStart("free")}
            disabled={!health.connected || loading}
            className="rounded-lg bg-zinc-700 px-5 py-2.5 text-sm font-medium text-white hover:bg-zinc-600 disabled:bg-zinc-800 disabled:cursor-not-allowed transition-colors"
          >
            Free Conversation
          </button>
        </div>
        {sessionError && (
          <p className="text-sm text-red-400">{sessionError}</p>
        )}
      </div>
    );
  }

  // Post-session: summary
  if (session.ended) {
    return (
      <div className="flex flex-col items-center gap-4">
        <p className="text-zinc-300">Session ended</p>
        <p className="text-sm text-zinc-500">
          {conversation.length} turns completed
        </p>
        <button
          onClick={() => {
            setConversation([]);
            // Reset session state by starting fresh
            handleStart("structured");
          }}
          className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-500 transition-colors"
        >
          New Session
        </button>
      </div>
    );
  }

  // Active session
  return (
    <div className="flex w-full max-w-lg flex-col items-center gap-4">
      {/* Activity card (structured mode) */}
      {session.currentActivity && session.plan && (
        <ActivityCard
          activity={session.currentActivity}
          index={session.currentActivityIndex}
          total={session.plan.activities.length}
          elapsedSec={activityElapsed}
        />
      )}

      {/* Mode badge (free mode) */}
      {session.mode === "free" && (
        <span className="rounded-full bg-zinc-800 px-3 py-1 text-xs text-zinc-400">
          Free conversation
        </span>
      )}

      {/* Conversation history */}
      <div
        ref={scrollRef}
        className="w-full max-h-64 overflow-y-auto space-y-3 scrollbar-thin"
      >
        {conversation.map((resp, i) => (
          <ConversationTurn
            key={i}
            response={resp}
            showMetrics={i === conversation.length - 1}
          />
        ))}
      </div>

      {/* Record button */}
      <button
        onClick={voice.recording ? voice.stopRecording : voice.startRecording}
        disabled={voice.processing || !health.connected}
        className={`flex h-20 w-20 items-center justify-center rounded-full text-2xl transition-all
          ${
            voice.recording
              ? "bg-red-600 shadow-lg shadow-red-600/30 animate-pulse"
              : voice.processing
                ? "bg-zinc-700 cursor-not-allowed"
                : "bg-blue-600 hover:bg-blue-500 shadow-lg shadow-blue-600/20 cursor-pointer"
          }`}
      >
        {voice.processing ? "..." : voice.recording ? "\u23F9" : "\u{1F3A4}"}
      </button>
      <p className="text-xs text-zinc-500">
        {voice.processing
          ? "Processing..."
          : voice.recording
            ? "Recording — click to stop"
            : "Click to speak"}
      </p>

      {/* Error */}
      {voice.error && (
        <p className="rounded-lg bg-red-900/50 px-4 py-2 text-xs text-red-300">
          {voice.error}
        </p>
      )}

      {/* End session button */}
      <button
        onClick={handleEnd}
        className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
      >
        End session
      </button>
    </div>
  );
}
