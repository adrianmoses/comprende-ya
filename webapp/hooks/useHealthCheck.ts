"use client";

import { useEffect, useRef, useState } from "react";
import { VOICE_AGENT_HEALTH_URL } from "@/lib/constants";

export interface HealthStatus {
  connected: boolean;
  gpu?: string;
}

export function useHealthCheck(intervalMs = 5000): HealthStatus {
  const [status, setStatus] = useState<HealthStatus>({ connected: false });
  const intervalRef = useRef<ReturnType<typeof setInterval>>(null);

  useEffect(() => {
    async function check() {
      try {
        const res = await fetch(VOICE_AGENT_HEALTH_URL);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        setStatus({ connected: true, gpu: data.gpu });
      } catch {
        setStatus({ connected: false });
      }
    }

    check();
    intervalRef.current = setInterval(check, intervalMs);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [intervalMs]);

  return status;
}
