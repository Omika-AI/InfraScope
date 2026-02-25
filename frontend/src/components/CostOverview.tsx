import { useCostOverview } from "@/hooks/useApi";
import { formatCost } from "@/utils/formatting";

export default function CostOverview() {
  const { costs, loading } = useCostOverview();

  if (loading && !costs) {
    return (
      <div className="bg-surface border border-border rounded-lg p-4 animate-pulse">
        <div className="h-5 bg-border rounded w-1/4 mb-3" />
        <div className="h-8 bg-border rounded w-1/3 mb-3" />
        <div className="h-3 bg-border rounded w-full" />
      </div>
    );
  }

  if (!costs) return null;

  const cloudPct =
    costs.total_monthly_eur > 0
      ? (costs.cloud_cost_eur / costs.total_monthly_eur) * 100
      : 0;

  return (
    <section className="bg-surface border border-border rounded-lg p-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        {/* Total cost */}
        <div>
          <h2 className="text-text-secondary text-xs font-medium uppercase tracking-wider mb-1">
            Monthly Cost
          </h2>
          <p className="text-text-primary text-2xl font-bold">
            {formatCost(costs.total_monthly_eur)}
            <span className="text-text-secondary text-sm font-normal">/mo</span>
          </p>
        </div>

        {/* Breakdown stats */}
        <div className="flex items-center gap-6">
          <div className="text-center">
            <p className="text-text-secondary text-xs mb-0.5">Cloud</p>
            <p className="text-text-primary text-sm font-semibold">
              {formatCost(costs.cloud_cost_eur)}
            </p>
          </div>
          <div className="text-center">
            <p className="text-text-secondary text-xs mb-0.5">Dedicated</p>
            <p className="text-text-primary text-sm font-semibold">
              {formatCost(costs.dedicated_cost_eur)}
            </p>
          </div>
          <div className="text-center">
            <p className="text-text-secondary text-xs mb-0.5">Servers</p>
            <p className="text-text-primary text-sm font-semibold">
              {costs.server_count}
            </p>
          </div>

          {/* Savings badge */}
          {costs.potential_savings_eur > 0 && (
            <div className="bg-idle/10 border border-idle/30 rounded-lg px-3 py-1.5 text-center">
              <p className="text-idle text-xs mb-0.5">Potential Savings</p>
              <p className="text-idle text-sm font-bold">
                {formatCost(costs.potential_savings_eur)}/mo
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Proportion bar */}
      <div className="mt-4">
        <div className="flex items-center gap-2 mb-1.5">
          <span className="text-text-secondary text-xs flex items-center gap-1">
            <span className="inline-block w-2 h-2 rounded-sm bg-moderate" />
            Cloud ({formatCost(costs.cloud_cost_eur)})
          </span>
          <span className="text-text-secondary text-xs flex items-center gap-1">
            <span className="inline-block w-2 h-2 rounded-sm bg-[#8b5cf6]" />
            Dedicated ({formatCost(costs.dedicated_cost_eur)})
          </span>
        </div>
        <div className="h-2 bg-border rounded-full overflow-hidden flex">
          <div
            className="bg-moderate h-full transition-all duration-500"
            style={{ width: `${cloudPct}%` }}
          />
          <div
            className="bg-[#8b5cf6] h-full transition-all duration-500"
            style={{ width: `${100 - cloudPct}%` }}
          />
        </div>
      </div>
    </section>
  );
}
