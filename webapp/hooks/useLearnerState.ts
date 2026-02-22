"use client";

import { useCallback, useState } from "react";
import { VOICE_AGENT_BASE_URL } from "@/lib/constants";
import type {
  StudiesState,
  ConfusionPair,
  EffectiveContext,
} from "@/lib/voice-protocol";

export function useLearnerState() {
  const [states, setStates] = useState<StudiesState[]>([]);
  const [confusions, setConfusions] = useState<ConfusionPair[]>([]);
  const [contexts, setContexts] = useState<EffectiveContext[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [statesRes, confusionsRes, contextsRes] = await Promise.all([
        fetch(`${VOICE_AGENT_BASE_URL}/learner/state`),
        fetch(`${VOICE_AGENT_BASE_URL}/learner/confusions`),
        fetch(`${VOICE_AGENT_BASE_URL}/learner/contexts`),
      ]);

      if (statesRes.ok) setStates(await statesRes.json());
      if (confusionsRes.ok) setConfusions(await confusionsRes.json());
      if (contextsRes.ok) setContexts(await contextsRes.json());
    } catch {
      // Keep previous data on error
    } finally {
      setLoading(false);
    }
  }, []);

  return { states, confusions, contexts, loading, fetchAll };
}
