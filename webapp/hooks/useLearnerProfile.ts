"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { VOICE_AGENT_BASE_URL } from "@/lib/constants";
import type { LearnerProfile } from "@/lib/voice-protocol";

export function useLearnerProfile(intervalMs = 30000) {
  const [profile, setProfile] = useState<LearnerProfile | null>(null);
  const [loading, setLoading] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval>>(null);

  const fetchProfile = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${VOICE_AGENT_BASE_URL}/learner/profile`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: LearnerProfile = await res.json();
      setProfile(data);
    } catch {
      // Keep previous data on error
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProfile();
    intervalRef.current = setInterval(fetchProfile, intervalMs);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchProfile, intervalMs]);

  return { profile, loading, refresh: fetchProfile };
}
