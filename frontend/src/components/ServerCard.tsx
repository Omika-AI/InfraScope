import type { Server } from "@/types";
import { formatCost, tierColor, tierLabel } from "@/utils/formatting";
import UtilizationGauge from "./UtilizationGauge";

interface ServerCardProps {
  server: Server;
  onSelect: (id: number) => void;
}

export default function ServerCard({ server, onSelect }: ServerCardProps) {
  const tier = server.metrics?.utilization_tier ?? "unknown";
  const color = tierColor(tier);
  const cpu = server.metrics?.cpu_percent ?? 0;
  const memory = server.metrics?.memory_percent ?? 0;

  return (
    <button
      type="button"
      onClick={() => onSelect(server.id)}
      className="bg-surface border border-border rounded-lg p-4 text-left transition-all duration-200 hover:border-[var(--hover-color)] hover:bg-input cursor-pointer w-full"
      style={
        { "--hover-color": color } as React.CSSProperties
      }
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="min-w-0">
          <h3 className="text-text-primary font-semibold text-sm truncate">
            {server.name}
          </h3>
          <p className="text-text-secondary text-xs mt-0.5">
            {server.server_type}
          </p>
        </div>
        <span
          className="text-xs font-medium px-2 py-0.5 rounded-full shrink-0 ml-2"
          style={{
            color,
            backgroundColor: `${color}18`,
          }}
        >
          {tierLabel(tier)}
        </span>
      </div>

      {/* Gauges */}
      <div className="space-y-1.5 mb-3">
        <UtilizationGauge label="CPU" percent={cpu} tier={tier} />
        <UtilizationGauge label="RAM" percent={memory} tier={tier} />
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between">
        <span className="text-text-primary text-sm font-medium">
          {formatCost(server.monthly_cost_eur)}/mo
        </span>
        <div className="flex items-center gap-2">
          <span className="text-text-secondary text-xs capitalize">
            {server.source}
          </span>
          <span
            className={`inline-block w-1.5 h-1.5 rounded-full ${
              server.status === "running" ? "bg-idle" : "bg-critical"
            }`}
          />
        </div>
      </div>
    </button>
  );
}
