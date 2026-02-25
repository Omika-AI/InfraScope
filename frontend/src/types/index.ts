export interface MetricSummary {
  cpu_percent: number;
  memory_percent: number;
  disk_percent: number;
  network_in_mbps: number;
  network_out_mbps: number;
  utilization_tier: string;
  avg_cpu_30d: number;
  avg_memory_30d: number;
  peak_cpu_30d: number;
  peak_memory_30d: number;
}

export interface Server {
  id: number;
  hetzner_id: string;
  name: string;
  server_type: string;
  source: string;
  status: string;
  datacenter: string;
  ipv4: string;
  cores: number;
  memory_gb: number;
  disk_gb: number;
  monthly_cost_eur: number;
  labels: Record<string, string> | null;
  project_name: string | null;
  last_seen_at: string;
  metrics: MetricSummary | null;
}

export interface MetricPoint {
  timestamp: string;
  cpu_percent: number;
  memory_percent: number;
  disk_percent: number;
  network_in_mbps: number;
  network_out_mbps: number;
  load_avg_1m: number | null;
}

export interface RunningService {
  id: number;
  service_type: string;
  name: string;
  port: number | null;
  status: string;
  cpu_percent: number | null;
  memory_mb: number | null;
  discovered_at: string;
  last_seen_at: string;
}

export interface CostOverview {
  total_monthly_eur: number;
  cloud_cost_eur: number;
  dedicated_cost_eur: number;
  potential_savings_eur: number;
  server_count: number;
  by_datacenter: { category: string; cost_eur: number; count: number }[];
  by_project: { category: string; cost_eur: number; count: number }[];
}

export interface CostHistoryPoint {
  month: string;
  total_eur: number;
  cloud_eur: number;
  dedicated_eur: number;
}

export interface Recommendation {
  id: number;
  group_name: string;
  server_ids: number[];
  target_server_type: string;
  current_total_cost_eur: number;
  projected_cost_eur: number;
  monthly_savings_eur: number;
  rationale: string;
  confidence: string;
  status: string;
  created_at: string;
}
