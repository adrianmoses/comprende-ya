import type { HealthStatus } from "@/hooks/useHealthCheck";

export function HealthIndicator({ status }: { status: HealthStatus }) {
  return (
    <div className="flex items-center gap-2 text-sm">
      <span
        className={`inline-block h-3 w-3 rounded-full ${
          status.connected ? "bg-green-500" : "bg-red-500"
        }`}
      />
      <span className="text-zinc-400">
        {status.connected
          ? `Voice agent connected${status.gpu ? ` — ${status.gpu}` : ""}`
          : "Voice agent offline"}
      </span>
    </div>
  );
}
