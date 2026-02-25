# InfraScope — Feature Status

## Core Backend

| Feature | Status | Notes |
|---------|--------|-------|
| FastAPI app with async/await | Done | Lifespan startup, CORS, 3 routers |
| Pydantic-settings config | Done | Multi-path .env loading, all intervals configurable |
| SQLAlchemy async + SQLite | Done | 4 models: Server, MetricSnapshot, RunningService, ConsolidationRecommendation |
| Pydantic response schemas | Done | Full request/response validation |
| APScheduler | Done | Collection (5m), analysis (1h), recommendations (24h) |

## Hetzner Integration

| Feature | Status | Notes |
|---------|--------|-------|
| Cloud API — list servers | Done | Paginated fetch, Bearer token auth |
| Cloud API — server metrics | Done | CPU, disk, network; normalized for multi-core |
| Cloud API — rate limit handling | Done | Exponential backoff on 429 |
| Robot API — list/get servers | Done | HTTP Basic Auth, dedicated server inventory |
| Real server sync | Done | 19 servers loaded from live Hetzner account |

## Collector Service

| Feature | Status | Notes |
|---------|--------|-------|
| Cloud server upsert | Done | Syncs name, type, cost, datacenter, labels, status |
| Dedicated server upsert | Done | Via Robot API |
| Cloud metric ingestion | Done | CPU normalized per-core, disk, network |
| Agent report ingestion | Done | POST /api/agent/report with shared secret |
| Stale server detection | Done | Flags servers not seen in 24h |
| Demo mode seeding | Done | 12 fake servers, 30 days hourly metrics, services |

## Analyzer Service

| Feature | Status | Notes |
|---------|--------|-------|
| Utilization classification | Done | idle / low / moderate / high / critical tiers |
| 30-day aggregates | Done | avg CPU, avg memory, peak CPU, peak memory |
| Per-server analysis | Done | Used by recommender and API responses |

## Recommender Service

| Feature | Status | Notes |
|---------|--------|-------|
| Rule 1 — Idle servers | Done | <5% avg CPU, suggests downsize or consolidation |
| Rule 2 — Staging/dev consolidation | Done | Groups by name/label pattern, picks target type |
| Rule 3 — Right-sizing | Done | Peak <30%, recommends next smaller tier |
| Cost calculation per recommendation | Done | Current vs projected cost, monthly savings |
| Clears stale pending recommendations | Done | Keeps accepted/dismissed intact |

## API Routes

| Endpoint | Status | Notes |
|----------|--------|-------|
| GET /api/servers | Done | Filter by source/status, search, sort |
| GET /api/servers/{id} | Done | Full detail with latest metrics summary |
| GET /api/servers/{id}/metrics | Done | Time-series, period param (7d/30d/90d) |
| GET /api/servers/{id}/services | Done | Running services list |
| GET /api/costs/overview | Done | Total, cloud/dedicated split, by datacenter/project |
| GET /api/costs/history | Done | Monthly cost trend (12 months) |
| GET /api/recommendations | Done | With status filter |
| POST /api/recommendations/{id}/accept | Done | |
| POST /api/recommendations/{id}/dismiss | Done | |
| POST /api/agent/report | Done | Agent secret auth |
| GET /api/health | Done | Includes demo_mode flag |

## Frontend

| Feature | Status | Notes |
|---------|--------|-------|
| Dashboard layout | Done | Header with last-sync timestamp, dark theme |
| Server grid | Done | Card grid with filter (All/Cloud/Dedicated), sort, search |
| Server card | Done | Name, type, CPU/RAM gauges, cost, utilization tier badge |
| Server detail panel | Done | Slide-out with header, gauges, metrics chart, services table, labels |
| Utilization gauge | Done | Horizontal bar with tier color coding |
| Metrics chart | Done | Recharts AreaChart, CPU+Memory overlay, tooltip, period selector |
| Cost overview | Done | Total spend, cloud/dedicated breakdown, datacenter/project tables, savings badge |
| Recommendations panel | Done | Collapsible, per-rec cards, accept/dismiss, total savings badge |
| Auto-refresh | Done | 60-second polling on all data hooks |
| Error handling | Done | Stale data shown with error banner, graceful degradation |
| Loading states | Done | Skeleton placeholders on all components |
| Dark theme | Done | Professional ops-center palette, consistent color coding |

## Agent (Dedicated Servers)

| Feature | Status | Notes |
|---------|--------|-------|
| Metric collection | Done | CPU, memory, disk, network, load average via psutil |
| Docker discovery | Done | `docker ps --format json` |
| Systemd discovery | Done | `systemctl list-units` |
| Port discovery | Done | `ss -tlnp` |
| 60-second reporting | Done | POST to /api/agent/report |
| Local queue + retry | Done | Queues reports when server unreachable, flushes on recovery |
| Install script | Done | Copies agent, installs psutil, sets up systemd service |
| Systemd unit file | Done | Auto-restart on failure |

## Docker & Deployment

| Feature | Status | Notes |
|---------|--------|-------|
| docker-compose.yml | Done | Backend + frontend services, volume for SQLite |
| Backend Dockerfile | Done | Python 3.12-slim, uvicorn |
| Frontend Dockerfile | Done | Multi-stage Node build + Nginx with API proxy |
| .env.example | Done | All configurable vars documented |

---

## Not Yet Implemented

| Feature | Priority | Notes |
|---------|----------|-------|
| Monthly cost trend chart | Medium | `useCostHistory` hook exists, CostOverview doesn't render a chart yet |
| Hetzner console quick link | Low | Server detail should link to `https://console.hetzner.cloud/servers/{id}` |
| Metric aggregation job | Medium | Spec: "aggregate to hourly for data older than 7 days" — needed to keep DB small long-term |

## Stretch Goals (Not Started — By Design)

| Feature | Notes |
|---------|-------|
| LLM-powered recommendations | Send inventory + metrics to Claude API for nuanced analysis |
| Terraform/Pulumi export | Generate IaC for recommended consolidations |
| GitHub integration | Link servers to repos via CI/CD metadata |
| Alerting (Slack/email) | Notify on critical utilization or 30+ day idle |
| Multi-provider support | Extend beyond Hetzner to AWS/GCP/DO |
