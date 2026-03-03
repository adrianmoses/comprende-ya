"use client";

import { useEffect, useRef, useState } from "react";
import { VOICE_AGENT_HEALTH_URL } from "@/lib/constants";

export interface HealthStatus {
  connected: boolean;
  warmingUp: boolean;
  gpu?: string;
}

export function useHealthCheck(intervalMs = 5000): HealthStatus {
  const [status, setStatus] = useState<HealthStatus>({ connected: false, warmingUp: false });
  const intervalRef = useRef<ReturnType<typeof setInterval>>(null);

  useEffect(() => {
    async function check() {
      try {
        const res = await fetch(VOICE_AGENT_HEALTH_URL);
        const data = await res.json();
        if (res.status === 503 && data.status === "warming_up") {
          setStatus({ connected: false, warmingUp: true });
        } else if (res.ok) {
          setStatus({ connected: true, warmingUp: false, gpu: data.gpu });
        } else {
          setStatus({ connected: false, warmingUp: false });
        }
      } catch {
        setStatus({ connected: false, warmingUp: false });
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
