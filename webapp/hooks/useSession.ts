"use client";

import { useCallback, useState } from "react";
import { VOICE_AGENT_BASE_URL } from "@/lib/constants";
import type {
  Activity,
  ActivityChangeMessage,
  ServerMessage,
  SessionEndMessage,
  SessionPlan,
  SessionPlanMessage,
} from "@/lib/voice-protocol";

export type SessionMode = "structured" | "free";

export interface SessionState {
  active: boolean;
  mode: SessionMode;
  plan: SessionPlan | null;
  currentActivityIndex: number;
  currentActivity: Activity | null;
  transitioning: boolean;
  ended: boolean;
  endReason: string | null;
}

export function useSession() {
  const [session, setSession] = useState<SessionState>({
    active: false,
    mode: "structured",
    plan: null,
    currentActivityIndex: 0,
    currentActivity: null,
    transitioning: false,
    ended: false,
    endReason: null,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const startSession = useCallback(
    async (mode: SessionMode, durationMin: number = 30) => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`${VOICE_AGENT_BASE_URL}/session/start`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ mode, duration_min: durationMin }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const plan = data.plan as SessionPlan | null;
        const activities = plan?.activities ?? [];

        setSession({
          active: true,
          mode,
          plan: plan && activities.length > 0 ? plan : null,
          currentActivityIndex: 0,
          currentActivity: activities[0] ?? null,
          transitioning: false,
          ended: false,
          endReason: null,
        });
        return plan;
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to start session"
        );
        return null;
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const endSession = useCallback(async () => {
    try {
      await fetch(`${VOICE_AGENT_BASE_URL}/session/end`, { method: "POST" });
    } catch {
      // Best effort
    }
    setSession((s) => ({
      ...s,
      active: false,
      ended: true,
      endReason: "user_ended",
    }));
  }, []);

  const handleServerMessage = useCallback((msg: ServerMessage) => {
    switch (msg.type) {
      case "session_plan": {
        const m = msg as SessionPlanMessage;
        const activities = m.plan.activities ?? [];
        setSession((s) => ({
          ...s,
          plan: activities.length > 0 ? m.plan : null,
          currentActivityIndex: 0,
          currentActivity: activities[0] ?? null,
        }));
        break;
      }
      case "activity_change": {
        const m = msg as ActivityChangeMessage;
        setSession((s) => ({
          ...s,
          currentActivityIndex: m.activity_index,
          currentActivity: m.activity,
          transitioning: false,
        }));
        break;
      }
      case "session_end": {
        const m = msg as SessionEndMessage;
        setSession((s) => ({
          ...s,
          active: false,
          ended: true,
          endReason: m.reason,
        }));
        break;
      }
    }
  }, []);

  return {
    session,
    loading,
    error,
    startSession,
    endSession,
    handleServerMessage,
  };
}
