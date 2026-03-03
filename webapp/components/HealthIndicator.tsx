import type { HealthStatus } from "@/hooks/useHealthCheck";

export function HealthIndicator({ status }: { status: HealthStatus }) {
  const color = status.connected
    ? "bg-green-500"
    : status.warmingUp
      ? "bg-yellow-500 animate-pulse"
      : "bg-red-500";

  const label = status.connected
    ? `Voice agent connected${status.gpu ? ` — ${status.gpu}` : ""}`
    : status.warmingUp
      ? "Warming up models..."
      : "Voice agent offline";

  return (
    <div className="flex items-center gap-2 text-sm">
      <span className={`inline-block h-3 w-3 rounded-full ${color}`} />
      <span className="text-zinc-400">{label}</span>
    </div>
  );
}
