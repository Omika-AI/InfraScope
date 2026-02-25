from datetime import datetime

from pydantic import BaseModel


# ── Server ──────────────────────────────────────────────

class MetricSummary(BaseModel):
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    disk_percent: float = 0.0
    network_in_mbps: float = 0.0
    network_out_mbps: float = 0.0
    utilization_tier: str = "moderate"
    avg_cpu_30d: float = 0.0
    avg_memory_30d: float = 0.0
    peak_cpu_30d: float = 0.0
    peak_memory_30d: float = 0.0


class ServerListItem(BaseModel):
    id: int
    hetzner_id: str
    name: str
    server_type: str
    source: str
    status: str
    datacenter: str
    ipv4: str
    cores: int
    memory_gb: float
    disk_gb: int
    monthly_cost_eur: float
    labels: dict | None = None
    project_name: str | None = None
    last_seen_at: datetime
    metrics: MetricSummary | None = None

    model_config = {"from_attributes": True}


class ServerDetail(ServerListItem):
    created_at: datetime
    updated_at: datetime


# ── Metrics ─────────────────────────────────────────────

class MetricPoint(BaseModel):
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    network_in_mbps: float
    network_out_mbps: float
    load_avg_1m: float | None = None

    model_config = {"from_attributes": True}


# ── Services ────────────────────────────────────────────

class RunningServiceItem(BaseModel):
    id: int
    service_type: str
    name: str
    port: int | None = None
    status: str
    cpu_percent: float | None = None
    memory_mb: float | None = None
    discovered_at: datetime
    last_seen_at: datetime

    model_config = {"from_attributes": True}


# ── Costs ───────────────────────────────────────────────

class CostBreakdown(BaseModel):
    category: str
    cost_eur: float
    count: int


class CostOverview(BaseModel):
    total_monthly_eur: float
    cloud_cost_eur: float
    dedicated_cost_eur: float
    potential_savings_eur: float
    server_count: int
    by_datacenter: list[CostBreakdown]
    by_project: list[CostBreakdown]


class CostHistoryPoint(BaseModel):
    month: str
    total_eur: float
    cloud_eur: float
    dedicated_eur: float


# ── Recommendations ─────────────────────────────────────

class RecommendationItem(BaseModel):
    id: int
    group_name: str
    server_ids: list[int]
    target_server_type: str
    current_total_cost_eur: float
    projected_cost_eur: float
    monthly_savings_eur: float
    rationale: str
    confidence: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Agent ───────────────────────────────────────────────

class AgentServiceReport(BaseModel):
    name: str
    service_type: str  # docker, systemd, port
    port: int | None = None
    status: str = "running"
    cpu_percent: float | None = None
    memory_mb: float | None = None


class AgentReport(BaseModel):
    hostname: str
    server_ip: str
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    network_in_mbps: float = 0.0
    network_out_mbps: float = 0.0
    load_avg_1m: float | None = None
    services: list[AgentServiceReport] = []
    secret: str


# ── Health ──────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    demo_mode: bool
    server_count: int
    last_collection: datetime | None = None
