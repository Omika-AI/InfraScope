"""Server, agent, and health API routes."""

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import MetricSnapshot, RunningService, Server, ServerSource, ServiceType
from app.schemas import (
    AgentReport,
    HealthResponse,
    MetricPoint,
    MetricSummary,
    RunningServiceItem,
    ServerDetail,
    ServerListItem,
)

router = APIRouter(tags=["Servers"])

# ── Helpers ──────────────────────────────────────────────


def _classify_utilization(avg_cpu_30d: float) -> str:
    """Classify server utilization based on 30-day average CPU usage."""
    if avg_cpu_30d < 5:
        return "idle"
    elif avg_cpu_30d < 20:
        return "low"
    elif avg_cpu_30d < 60:
        return "moderate"
    elif avg_cpu_30d < 85:
        return "high"
    else:
        return "critical"


def _parse_period(period: str) -> datetime:
    """Convert a period string like '7d', '30d', '90d' into a cutoff datetime."""
    mapping = {"7d": 7, "30d": 30, "90d": 90}
    days = mapping.get(period, 30)
    return datetime.now(timezone.utc) - timedelta(days=days)


async def _build_metric_summary(
    db: AsyncSession, server_id: int
) -> MetricSummary | None:
    """Build a MetricSummary for a server using its latest snapshot and 30-day aggregates."""
    cutoff_30d = datetime.now(timezone.utc) - timedelta(days=30)

    # Latest snapshot
    latest_stmt = (
        select(MetricSnapshot)
        .where(MetricSnapshot.server_id == server_id)
        .order_by(MetricSnapshot.timestamp.desc())
        .limit(1)
    )
    latest_result = await db.execute(latest_stmt)
    latest: MetricSnapshot | None = latest_result.scalar_one_or_none()

    if latest is None:
        return None

    # 30-day aggregates
    agg_stmt = select(
        func.avg(MetricSnapshot.cpu_percent),
        func.avg(MetricSnapshot.memory_percent),
        func.max(MetricSnapshot.cpu_percent),
        func.max(MetricSnapshot.memory_percent),
    ).where(
        MetricSnapshot.server_id == server_id,
        MetricSnapshot.timestamp >= cutoff_30d,
    )
    agg_result = await db.execute(agg_stmt)
    row = agg_result.one()

    avg_cpu = row[0] or 0.0
    avg_mem = row[1] or 0.0
    peak_cpu = row[2] or 0.0
    peak_mem = row[3] or 0.0

    return MetricSummary(
        cpu_percent=latest.cpu_percent,
        memory_percent=latest.memory_percent,
        disk_percent=latest.disk_percent,
        network_in_mbps=latest.network_in_mbps,
        network_out_mbps=latest.network_out_mbps,
        utilization_tier=_classify_utilization(avg_cpu),
        avg_cpu_30d=round(avg_cpu, 1),
        avg_memory_30d=round(avg_mem, 1),
        peak_cpu_30d=round(peak_cpu, 1),
        peak_memory_30d=round(peak_mem, 1),
    )


# ── Server List ──────────────────────────────────────────


@router.get("/servers", response_model=list[ServerListItem])
async def list_servers(
    db: Annotated[AsyncSession, Depends(get_db)],
    source: Annotated[str | None, Query(description="Filter by source: cloud or dedicated")] = None,
    status: Annotated[str | None, Query(description="Filter by status: running, stopped, etc.")] = None,
    sort_by: Annotated[str, Query(description="Sort by: name, cost, or cpu")] = "name",
    search: Annotated[str | None, Query(description="Search by server name")] = None,
) -> list[ServerListItem]:
    """List all servers with latest metrics summary."""
    stmt = select(Server)

    if source is not None:
        stmt = stmt.where(Server.source == source)
    if status is not None:
        stmt = stmt.where(Server.status == status)
    if search is not None:
        stmt = stmt.where(Server.name.ilike(f"%{search}%"))

    result = await db.execute(stmt)
    servers = result.scalars().all()

    items: list[ServerListItem] = []
    for srv in servers:
        summary = await _build_metric_summary(db, srv.id)
        item = ServerListItem(
            id=srv.id,
            hetzner_id=srv.hetzner_id,
            name=srv.name,
            server_type=srv.server_type,
            source=srv.source.value,
            status=srv.status,
            datacenter=srv.datacenter,
            ipv4=srv.ipv4,
            cores=srv.cores,
            memory_gb=srv.memory_gb,
            disk_gb=srv.disk_gb,
            monthly_cost_eur=srv.monthly_cost_eur,
            labels=srv.labels,
            project_name=srv.project_name,
            last_seen_at=srv.last_seen_at,
            metrics=summary,
        )
        items.append(item)

    # Sort results
    if sort_by == "cost":
        items.sort(key=lambda s: s.monthly_cost_eur, reverse=True)
    elif sort_by == "cpu":
        items.sort(
            key=lambda s: (s.metrics.cpu_percent if s.metrics else 0.0),
            reverse=True,
        )
    else:
        # Default: sort by name
        items.sort(key=lambda s: s.name.lower())

    return items


# ── Server Detail ────────────────────────────────────────


@router.get("/servers/{server_id}", response_model=ServerDetail)
async def get_server(
    server_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ServerDetail:
    """Get detailed information for a single server."""
    stmt = select(Server).where(Server.id == server_id)
    result = await db.execute(stmt)
    srv = result.scalar_one_or_none()

    if srv is None:
        raise HTTPException(status_code=404, detail="Server not found")

    summary = await _build_metric_summary(db, srv.id)

    return ServerDetail(
        id=srv.id,
        hetzner_id=srv.hetzner_id,
        name=srv.name,
        server_type=srv.server_type,
        source=srv.source.value,
        status=srv.status,
        datacenter=srv.datacenter,
        ipv4=srv.ipv4,
        cores=srv.cores,
        memory_gb=srv.memory_gb,
        disk_gb=srv.disk_gb,
        monthly_cost_eur=srv.monthly_cost_eur,
        labels=srv.labels,
        project_name=srv.project_name,
        last_seen_at=srv.last_seen_at,
        created_at=srv.created_at,
        updated_at=srv.updated_at,
        metrics=summary,
    )


# ── Server Metrics (time-series) ────────────────────────


@router.get("/servers/{server_id}/metrics", response_model=list[MetricPoint])
async def get_server_metrics(
    server_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    period: Annotated[str, Query(description="Time period: 7d, 30d, or 90d")] = "30d",
) -> list[MetricPoint]:
    """Return time-series metric snapshots for a server over the requested period."""
    # Verify server exists
    srv_result = await db.execute(select(Server.id).where(Server.id == server_id))
    if srv_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Server not found")

    cutoff = _parse_period(period)
    stmt = (
        select(MetricSnapshot)
        .where(
            MetricSnapshot.server_id == server_id,
            MetricSnapshot.timestamp >= cutoff,
        )
        .order_by(MetricSnapshot.timestamp.asc())
    )
    result = await db.execute(stmt)
    snapshots = result.scalars().all()

    return [MetricPoint.model_validate(snap) for snap in snapshots]


# ── Server Services ──────────────────────────────────────


@router.get("/servers/{server_id}/services", response_model=list[RunningServiceItem])
async def get_server_services(
    server_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[RunningServiceItem]:
    """List running services discovered on a server."""
    # Verify server exists
    srv_result = await db.execute(select(Server.id).where(Server.id == server_id))
    if srv_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Server not found")

    stmt = (
        select(RunningService)
        .where(RunningService.server_id == server_id)
        .order_by(RunningService.name.asc())
    )
    result = await db.execute(stmt)
    services = result.scalars().all()

    return [RunningServiceItem.model_validate(svc) for svc in services]


# ── Agent Report ─────────────────────────────────────────


@router.post("/agent/report")
async def agent_report(
    report: AgentReport,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """Receive a metric and service report from a dedicated server agent."""
    # Validate agent secret
    if report.secret != settings.agent_secret:
        raise HTTPException(status_code=403, detail="Invalid agent secret")

    now = datetime.now(timezone.utc)

    # Find or create the server by IP
    stmt = select(Server).where(Server.ipv4 == report.server_ip)
    result = await db.execute(stmt)
    srv = result.scalar_one_or_none()

    if srv is None:
        # Auto-register as a dedicated server
        srv = Server(
            hetzner_id=f"agent-{report.server_ip}",
            name=report.hostname,
            server_type="dedicated",
            source=ServerSource.dedicated,
            status="running",
            ipv4=report.server_ip,
            last_seen_at=now,
        )
        db.add(srv)
        await db.flush()  # populate srv.id
    else:
        srv.last_seen_at = now
        srv.name = report.hostname

    # Insert metric snapshot
    snapshot = MetricSnapshot(
        server_id=srv.id,
        timestamp=now,
        cpu_percent=report.cpu_percent,
        memory_percent=report.memory_percent,
        disk_percent=report.disk_percent,
        network_in_mbps=report.network_in_mbps,
        network_out_mbps=report.network_out_mbps,
        load_avg_1m=report.load_avg_1m,
    )
    db.add(snapshot)

    # Upsert running services:
    # Remove stale services for this server, then insert fresh ones
    await db.execute(
        delete(RunningService).where(RunningService.server_id == srv.id)
    )

    for svc_report in report.services:
        svc = RunningService(
            server_id=srv.id,
            service_type=ServiceType(svc_report.service_type),
            name=svc_report.name,
            port=svc_report.port,
            status=svc_report.status,
            cpu_percent=svc_report.cpu_percent,
            memory_mb=svc_report.memory_mb,
            discovered_at=now,
            last_seen_at=now,
        )
        db.add(svc)

    await db.commit()
    return {"status": "ok"}


# ── Health Check ─────────────────────────────────────────


@router.get("/health", response_model=HealthResponse)
async def health_check(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HealthResponse:
    """Return application health status."""
    count_result = await db.execute(select(func.count(Server.id)))
    server_count = count_result.scalar_one()

    # Get the latest metric timestamp as a proxy for last collection time
    latest_stmt = (
        select(MetricSnapshot.timestamp)
        .order_by(MetricSnapshot.timestamp.desc())
        .limit(1)
    )
    latest_result = await db.execute(latest_stmt)
    last_collection = latest_result.scalar_one_or_none()

    return HealthResponse(
        status="ok",
        demo_mode=settings.demo_mode,
        server_count=server_count,
        last_collection=last_collection,
    )
