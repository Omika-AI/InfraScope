import { formatPercent, tierColor } from "@/utils/formatting";

interface UtilizationGaugeProps {
  label: string;
  percent: number;
  tier: string;
}

export default function UtilizationGauge({
  label,
  percent,
  tier,
}: UtilizationGaugeProps) {
  const color = tierColor(tier);
  const clampedPercent = Math.min(100, Math.max(0, percent));

  return (
    <div className="flex items-center gap-2">
      <span className="text-text-secondary text-xs w-8 shrink-0">{label}</span>
      <div className="flex-1 h-2 bg-border rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{
            width: `${clampedPercent}%`,
            backgroundColor: color,
          }}
        />
      </div>
      <span className="text-text-secondary text-xs w-12 text-right shrink-0">
        {formatPercent(percent)}
      </span>
    </div>
  );
}
