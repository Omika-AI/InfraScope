import { useState } from "react";
import {
  useRecommendations,
  dismissRecommendation,
  acceptRecommendation,
} from "@/hooks/useApi";
import type { Recommendation } from "@/types";
import { formatCost, timeAgo } from "@/utils/formatting";

export default function Recommendations() {
  const { recommendations, loading, refetch } = useRecommendations();
  const [expanded, setExpanded] = useState(true);
  const [acting, setActing] = useState<number | null>(null);

  const active = recommendations?.filter((r) => r.status === "pending") ?? [];

  async function handleAction(
    id: number,
    action: "accept" | "dismiss"
  ) {
    setActing(id);
    try {
      if (action === "accept") {
        await acceptRecommendation(id);
      } else {
        await dismissRecommendation(id);
      }
      refetch();
    } catch {
      // Silently handle - data will be stale until next refresh
    } finally {
      setActing(null);
    }
  }

  if (loading && !recommendations) {
    return (
      <div className="bg-surface border border-border rounded-lg p-4 animate-pulse">
        <div className="h-5 bg-border rounded w-1/3 mb-3" />
        <div className="h-12 bg-border rounded w-full mb-2" />
        <div className="h-12 bg-border rounded w-full" />
      </div>
    );
  }

  if (active.length === 0) return null;

  const totalSavings = active.reduce((sum, r) => sum + r.monthly_savings_eur, 0);

  function confidenceDot(confidence: string) {
    const colors: Record<string, string> = {
      high: "bg-idle",
      medium: "bg-low",
      low: "bg-text-secondary",
    };
    return (
      <span className="flex items-center gap-1 text-xs text-text-secondary">
        <span
          className={`inline-block w-1.5 h-1.5 rounded-full ${colors[confidence] ?? "bg-text-secondary"}`}
        />
        {confidence}
      </span>
    );
  }

  return (
    <section className="bg-surface border border-border rounded-lg overflow-hidden">
      {/* Collapsible header */}
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-input transition-colors cursor-pointer"
      >
        <h2 className="text-text-primary text-sm font-semibold flex items-center gap-2">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="w-4 h-4 text-low"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M9.663 17h4.674M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
            />
          </svg>
          Recommendations
          <span className="bg-low/20 text-low text-xs px-1.5 py-0.5 rounded-full font-medium">
            {active.length}
          </span>
          <span className="bg-idle/10 text-idle text-xs px-2 py-0.5 rounded-full font-semibold ml-1">
            Save {formatCost(totalSavings)}/mo
          </span>
        </h2>
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className={`w-4 h-4 text-text-secondary transition-transform ${expanded ? "rotate-180" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </button>

      {/* Content */}
      {expanded && (
        <div className="border-t border-border divide-y divide-border/50">
          {active.map((rec: Recommendation) => (
            <div
              key={rec.id}
              className="px-4 py-3 flex items-start gap-3"
            >
              {/* Icon */}
              <div className="mt-0.5 shrink-0 w-6 h-6 rounded-full bg-idle/10 flex items-center justify-center">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  className="w-3.5 h-3.5 text-idle"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
              </div>

              {/* Details */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-0.5">
                  <h3 className="text-text-primary text-sm font-medium truncate">
                    {rec.group_name}
                  </h3>
                  {confidenceDot(rec.confidence)}
                </div>
                <p className="text-text-secondary text-xs leading-relaxed mb-2">
                  {rec.rationale}
                </p>
                <div className="flex items-center gap-3 text-xs text-text-secondary">
                  <span>
                    Target: <span className="text-text-primary">{rec.target_server_type}</span>
                  </span>
                  <span>
                    Current: <span className="text-text-primary">{formatCost(rec.current_total_cost_eur)}/mo</span>
                  </span>
                  <span>
                    Projected: <span className="text-text-primary">{formatCost(rec.projected_cost_eur)}/mo</span>
                  </span>
                  <span className="text-text-secondary">{timeAgo(rec.created_at)}</span>
                </div>
              </div>

              {/* Savings + Actions */}
              <div className="shrink-0 flex flex-col items-end gap-2">
                <span className="text-idle font-bold text-sm">
                  -{formatCost(rec.monthly_savings_eur)}/mo
                </span>
                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    disabled={acting === rec.id}
                    onClick={() => handleAction(rec.id, "accept")}
                    className="text-xs px-2 py-1 rounded text-idle hover:bg-idle/10 transition-colors disabled:opacity-50 cursor-pointer"
                  >
                    Accept
                  </button>
                  <button
                    type="button"
                    disabled={acting === rec.id}
                    onClick={() => handleAction(rec.id, "dismiss")}
                    className="text-xs px-2 py-1 rounded text-text-secondary hover:bg-input transition-colors disabled:opacity-50 cursor-pointer"
                  >
                    Dismiss
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
