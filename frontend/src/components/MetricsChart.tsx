import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { MetricPoint } from "@/types";
import { formatTimestamp, formatPercent, formatShortDate } from "@/utils/formatting";

interface MetricsChartProps {
  data: MetricPoint[];
  height?: number;
}

interface TooltipPayloadEntry {
  name: string;
  value: number;
  color: string;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
  label?: string;
}

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload || !label) return null;

  return (
    <div className="bg-surface border border-border rounded-lg px-3 py-2 shadow-lg">
      <p className="text-text-secondary text-xs mb-1">
        {formatTimestamp(label)}
      </p>
      {payload.map((entry) => (
        <p
          key={entry.name}
          className="text-sm"
          style={{ color: entry.color }}
        >
          {entry.name}: {formatPercent(entry.value)}
        </p>
      ))}
    </div>
  );
}

export default function MetricsChart({ data, height = 280 }: MetricsChartProps) {
  if (!data || data.length === 0) {
    return (
      <div
        className="flex items-center justify-center text-text-secondary text-sm"
        style={{ height }}
      >
        No metrics data available
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="cpuGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.3} />
            <stop offset="100%" stopColor="#3b82f6" stopOpacity={0.02} />
          </linearGradient>
          <linearGradient id="memoryGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.3} />
            <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#2a2d35" vertical={false} />
        <XAxis
          dataKey="timestamp"
          tickFormatter={formatShortDate}
          stroke="#94a3b8"
          fontSize={11}
          tickLine={false}
          axisLine={{ stroke: "#2a2d35" }}
        />
        <YAxis
          domain={[0, 100]}
          tickFormatter={(v: number) => `${v}%`}
          stroke="#94a3b8"
          fontSize={11}
          tickLine={false}
          axisLine={false}
          width={45}
        />
        <Tooltip content={<CustomTooltip />} />
        <Area
          type="monotone"
          dataKey="cpu_percent"
          name="CPU"
          stroke="#3b82f6"
          strokeWidth={2}
          fill="url(#cpuGradient)"
          dot={false}
          activeDot={{ r: 4, fill: "#3b82f6", stroke: "#0f1117", strokeWidth: 2 }}
        />
        <Area
          type="monotone"
          dataKey="memory_percent"
          name="Memory"
          stroke="#8b5cf6"
          strokeWidth={2}
          fill="url(#memoryGradient)"
          dot={false}
          activeDot={{ r: 4, fill: "#8b5cf6", stroke: "#0f1117", strokeWidth: 2 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
