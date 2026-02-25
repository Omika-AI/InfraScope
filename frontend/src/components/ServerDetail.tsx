import { useState } from "react";
import { useServer, useMetrics, useServices } from "@/hooks/useApi";
import type { RunningService } from "@/types";
import {
  formatCost,
  formatPercent,
  timeAgo,
  tierColor,
  tierLabel,
} from "@/utils/formatting";
import MetricsChart from "./MetricsChart";
import UtilizationGauge from "./UtilizationGauge";

interface ServerDetailProps {
  serverId: number;
  onClose: () => void;
}

type Period = "7d" | "30d" | "90d";

export default function ServerDetail({ serverId, onClose }: ServerDetailProps) {
  const [period, setPeriod] = useState<Period>("7d");
  const { server, loading: serverLoading } = useServer(serverId);
  const { metrics, loading: metricsLoading } = useMetrics(serverId, period);
  const { services } = useServices(serverId);

  const tier = server?.metrics?.utilization_tier ?? "unknown";
  const color = tierColor(tier);

  return (
    <>
      {/* Overlay */}
      <div
        className="fixed inset-0 bg-black/50 z-40"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="fixed top-0 right-0 bottom-0 w-full max-w-2xl bg-background border-l border-border z-50 overflow-y-auto">
        {/* Close button */}
        <button
          type="button"
          onClick={onClose}
          className="absolute top-4 right-4 text-text-secondary hover:text-text-primary transition-colors p-1 z-10 cursor-pointer"
          aria-label="Close"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="w-5 h-5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>

        {serverLoading && !server ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-text-secondary text-sm">Loading...</div>
          </div>
        ) : server ? (
          <div className="p-6">
            {/* Header */}
            <div className="mb-6">
              <div className="flex items-start gap-3 mb-2">
                <h2 className="text-text-primary text-xl font-bold">
                  {server.name}
                </h2>
                <span
                  className="text-xs font-medium px-2 py-0.5 rounded-full mt-1"
                  style={{
                    color,
                    backgroundColor: `${color}18`,
                  }}
                >
                  {tierLabel(tier)}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
                <div>
                  <span className="text-text-secondary">Type: </span>
                  <span className="text-text-primary">{server.server_type}</span>
                </div>
                <div>
                  <span className="text-text-secondary">Source: </span>
                  <span className="text-text-primary capitalize">
                    {server.source}
                  </span>
                </div>
                <div>
                  <span className="text-text-secondary">IP: </span>
                  <span className="text-text-primary font-mono text-xs">
                    {server.ipv4}
                  </span>
                </div>
                <div>
                  <span className="text-text-secondary">Datacenter: </span>
                  <span className="text-text-primary">{server.datacenter}</span>
                </div>
                <div>
                  <span className="text-text-secondary">Specs: </span>
                  <span className="text-text-primary">
                    {server.cores} vCPU / {server.memory_gb}GB / {server.disk_gb}
                    GB
                  </span>
                </div>
                <div>
                  <span className="text-text-secondary">Cost: </span>
                  <span className="text-text-primary font-semibold">
                    {formatCost(server.monthly_cost_eur)}/mo
                  </span>
                </div>
                <div>
                  <span className="text-text-secondary">Status: </span>
                  <span
                    className={
                      server.status === "running"
                        ? "text-idle"
                        : "text-critical"
                    }
                  >
                    {server.status}
                  </span>
                </div>
                <div>
                  <span className="text-text-secondary">Last seen: </span>
                  <span className="text-text-primary">
                    {timeAgo(server.last_seen_at)}
                  </span>
                </div>
              </div>

              {/* Project & Labels */}
              {server.project_name && (
                <div className="mt-2 text-sm">
                  <span className="text-text-secondary">Project: </span>
                  <span className="text-moderate">{server.project_name}</span>
                </div>
              )}
              {server.labels && Object.keys(server.labels).length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {Object.entries(server.labels).map(([key, val]) => (
                    <span
                      key={key}
                      className="bg-input border border-border text-text-secondary text-xs px-2 py-0.5 rounded"
                    >
                      {key}: {val}
                    </span>
                  ))}
                </div>
              )}
            </div>

            {/* Current utilization */}
            {server.metrics && (
              <div className="bg-surface border border-border rounded-lg p-4 mb-6">
                <h3 className="text-text-primary text-sm font-semibold mb-3">
                  Current Utilization
                </h3>
                <div className="space-y-2">
                  <UtilizationGauge
                    label="CPU"
                    percent={server.metrics.cpu_percent}
                    tier={tier}
                  />
                  <UtilizationGauge
                    label="RAM"
                    percent={server.metrics.memory_percent}
                    tier={tier}
                  />
                  <UtilizationGauge
                    label="Disk"
                    percent={server.metrics.disk_percent}
                    tier={tier}
                  />
                </div>
                <div className="grid grid-cols-2 gap-4 mt-3 text-xs text-text-secondary">
                  <div>
                    30d Avg CPU:{" "}
                    <span className="text-text-primary">
                      {formatPercent(server.metrics.avg_cpu_30d)}
                    </span>
                  </div>
                  <div>
                    30d Peak CPU:{" "}
                    <span className="text-text-primary">
                      {formatPercent(server.metrics.peak_cpu_30d)}
                    </span>
                  </div>
                  <div>
                    30d Avg RAM:{" "}
                    <span className="text-text-primary">
                      {formatPercent(server.metrics.avg_memory_30d)}
                    </span>
                  </div>
                  <div>
                    30d Peak RAM:{" "}
                    <span className="text-text-primary">
                      {formatPercent(server.metrics.peak_memory_30d)}
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* Metrics chart */}
            <div className="bg-surface border border-border rounded-lg p-4 mb-6">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-text-primary text-sm font-semibold">
                  Metrics History
                </h3>
                <div className="flex gap-1">
                  {(["7d", "30d", "90d"] as Period[]).map((p) => (
                    <button
                      key={p}
                      type="button"
                      onClick={() => setPeriod(p)}
                      className={`px-2.5 py-1 rounded text-xs font-medium transition-colors cursor-pointer ${
                        period === p
                          ? "bg-moderate text-white"
                          : "text-text-secondary hover:text-text-primary hover:bg-input"
                      }`}
                    >
                      {p}
                    </button>
                  ))}
                </div>
              </div>

              {metricsLoading && !metrics ? (
                <div className="h-[280px] flex items-center justify-center text-text-secondary text-sm">
                  Loading metrics...
                </div>
              ) : (
                <MetricsChart data={metrics ?? []} height={280} />
              )}

              <div className="flex items-center gap-4 mt-2 text-xs text-text-secondary">
                <span className="flex items-center gap-1.5">
                  <span className="inline-block w-3 h-0.5 bg-moderate rounded" />
                  CPU
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="inline-block w-3 h-0.5 bg-[#8b5cf6] rounded" />
                  Memory
                </span>
              </div>
            </div>

            {/* Services table */}
            <div className="bg-surface border border-border rounded-lg p-4">
              <h3 className="text-text-primary text-sm font-semibold mb-3">
                Running Services
                {services && (
                  <span className="text-text-secondary font-normal ml-1">
                    ({services.length})
                  </span>
                )}
              </h3>

              {services && services.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-text-secondary text-xs border-b border-border">
                        <th className="text-left py-2 pr-3 font-medium">
                          Name
                        </th>
                        <th className="text-left py-2 pr-3 font-medium">
                          Type
                        </th>
                        <th className="text-left py-2 pr-3 font-medium">
                          Port
                        </th>
                        <th className="text-right py-2 pr-3 font-medium">
                          CPU
                        </th>
                        <th className="text-right py-2 pr-3 font-medium">
                          Memory
                        </th>
                        <th className="text-left py-2 font-medium">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {services.map((svc: RunningService) => (
                        <tr
                          key={svc.id}
                          className="border-b border-border/50 last:border-0"
                        >
                          <td className="py-2 pr-3 text-text-primary font-mono text-xs truncate max-w-[180px]">
                            {svc.name}
                          </td>
                          <td className="py-2 pr-3">
                            <span className="text-xs px-1.5 py-0.5 rounded bg-input text-text-secondary capitalize">
                              {svc.service_type}
                            </span>
                          </td>
                          <td className="py-2 pr-3 text-text-secondary font-mono text-xs">
                            {svc.port ?? "--"}
                          </td>
                          <td className="py-2 pr-3 text-right text-text-primary text-xs">
                            {svc.cpu_percent != null
                              ? formatPercent(svc.cpu_percent)
                              : "--"}
                          </td>
                          <td className="py-2 pr-3 text-right text-text-primary text-xs">
                            {svc.memory_mb != null
                              ? `${svc.memory_mb.toFixed(0)} MB`
                              : "--"}
                          </td>
                          <td className="py-2">
                            <span
                              className={`text-xs ${
                                svc.status === "running"
                                  ? "text-idle"
                                  : "text-text-secondary"
                              }`}
                            >
                              {svc.status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-text-secondary text-sm">
                  No services discovered.
                </p>
              )}
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-center h-full">
            <div className="text-text-secondary text-sm">
              Server not found.
            </div>
          </div>
        )}
      </div>
    </>
  );
}
