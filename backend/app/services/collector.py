"""Metric collection orchestrator.

Responsible for syncing server inventory and metrics from both the Hetzner
Cloud API and the Hetzner Robot API, as well as seeding realistic demo data
when ``DEMO_MODE=true``.
"""

from __future__ import annotations

import logging
import math
import random
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import (
    MetricSnapshot,
    RunningService,
    Server,
    ServerSource,
    ServiceType,
)
from app.services import hetzner_cloud, hetzner_robot

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cloud server collection
# ---------------------------------------------------------------------------

async def collect_cloud_servers(db: AsyncSession) -> None:
    """Fetch all cloud servers and their metrics from the Hetzner Cloud API.

    Performs an upsert into the ``Server`` table (matched on ``hetzner_id``)
    and inserts a new ``MetricSnapshot`` for each server.
    """
    logger.info("Collecting cloud servers from Hetzner Cloud API")

    try:
        raw_servers = await hetzner_cloud.list_servers()
    except Exception:
        logger.exception("Failed to fetch cloud servers")
        return

    # Optionally fetch server type pricing for cost mapping
    price_map = await _build_cloud_price_map()

    now = datetime.now(timezone.utc)

    for raw in raw_servers:
        hetzner_id = str(raw["id"])
        server_type_name = (
            raw.get("server_type", {}).get("name", "unknown")
            if isinstance(raw.get("server_type"), dict)
            else str(raw.get("server_type", "unknown"))
        )

        # Extract specs from the server type object when available
        st = raw.get("server_type", {}) if isinstance(raw.get("server_type"), dict) else {}
        cores = int(st.get("cores", 0))
        memory_gb = float(st.get("memory", 0))
        disk_gb = int(st.get("disk", 0))

        # Pricing
        monthly_cost = _extract_monthly_price(st, price_map, server_type_name)

        # Datacenter
        dc = raw.get("datacenter", {})
        datacenter = dc.get("name", "") if isinstance(dc, dict) else str(dc)

        # Public IP
        public_net = raw.get("public_net", {})
        ipv4 = ""
        if isinstance(public_net, dict):
            ipv4_data = public_net.get("ipv4", {})
            ipv4 = ipv4_data.get("ip", "") if isinstance(ipv4_data, dict) else str(ipv4_data)

        # Upsert server
        result = await db.execute(
            select(Server).where(Server.hetzner_id == hetzner_id)
        )
        server = result.scalar_one_or_none()

        if server is None:
            server = Server(
                hetzner_id=hetzner_id,
                name=raw.get("name", hetzner_id),
                server_type=server_type_name,
                source=ServerSource.cloud,
                status=raw.get("status", "running"),
                datacenter=datacenter,
                ipv4=ipv4,
                cores=cores,
                memory_gb=memory_gb,
                disk_gb=disk_gb,
                monthly_cost_eur=monthly_cost,
                labels=raw.get("labels", {}),
                created_at=now,
                last_seen_at=now,
            )
            db.add(server)
        else:
            server.name = raw.get("name", server.name)
            server.server_type = server_type_name
            server.status = raw.get("status", server.status)
            server.datacenter = datacenter
            server.ipv4 = ipv4
            server.cores = cores
            server.memory_gb = memory_gb
            server.disk_gb = disk_gb
            server.monthly_cost_eur = monthly_cost
            server.labels = raw.get("labels", server.labels)
            server.last_seen_at = now

        await db.flush()

        # Fetch and store metrics
        await _collect_cloud_metrics(db, server, hetzner_id)

    await db.commit()
    logger.info("Cloud server collection complete (%d servers)", len(raw_servers))


async def _collect_cloud_metrics(
    db: AsyncSession,
    server: Server,
    hetzner_id: str,
) -> None:
    """Pull the latest CPU metrics from Hetzner Cloud API for one server."""
    now = datetime.now(timezone.utc)
    start = now - timedelta(minutes=10)

    try:
        cpu_data = await hetzner_cloud.get_server_metrics(
            hetzner_id, "cpu", start, now
        )
    except Exception:
        logger.debug("Failed to fetch metrics for cloud server %s", hetzner_id)
        return

    # Hetzner returns { metrics: { time_series: { cpu: { values: [[ts, val], ...] } } } }
    metrics_obj = cpu_data.get("metrics", {})
    timeseries = metrics_obj.get("time_series") or metrics_obj.get("timeseries", {})

    cpu_values: list[float] = []
    for _name, series in timeseries.items():
        for point in series.get("values", []):
            if len(point) >= 2:
                try:
                    cpu_values.append(float(point[1]))
                except (ValueError, TypeError):
                    pass

    if not cpu_values:
        return

    avg_cpu = sum(cpu_values) / len(cpu_values)
    # Hetzner reports CPU summed across cores — normalize to 0-100%
    if server.cores > 0 and avg_cpu > 100:
        avg_cpu = avg_cpu / server.cores
    avg_cpu = min(100.0, avg_cpu)

    # Also fetch disk and network metrics
    disk_pct = 0.0
    net_in = 0.0
    net_out = 0.0

    try:
        disk_data = await hetzner_cloud.get_server_metrics(hetzner_id, "disk", start, now)
        disk_ts = (disk_data.get("metrics", {}).get("time_series") or
                   disk_data.get("metrics", {}).get("timeseries", {}))
        for _name, series in disk_ts.items():
            vals = [float(p[1]) for p in series.get("values", []) if len(p) >= 2]
            if vals and "bandwidth.read" not in _name and "bandwidth.write" not in _name:
                disk_pct = max(disk_pct, sum(vals) / len(vals))
    except Exception:
        pass

    try:
        net_data = await hetzner_cloud.get_server_metrics(hetzner_id, "network", start, now)
        net_ts = (net_data.get("metrics", {}).get("time_series") or
                  net_data.get("metrics", {}).get("timeseries", {}))
        for _name, series in net_ts.items():
            vals = [float(p[1]) for p in series.get("values", []) if len(p) >= 2]
            if vals:
                avg_val = sum(vals) / len(vals)
                # Network values are in bytes/s, convert to Mbps
                mbps = avg_val * 8 / 1_000_000
                if "in" in _name:
                    net_in = mbps
                elif "out" in _name:
                    net_out = mbps
    except Exception:
        pass

    snapshot = MetricSnapshot(
        server_id=server.id,
        timestamp=now,
        cpu_percent=round(avg_cpu, 2),
        memory_percent=0.0,  # Hetzner Cloud API doesn't expose memory %
        disk_percent=round(disk_pct, 2),
        network_in_mbps=round(net_in, 4),
        network_out_mbps=round(net_out, 4),
    )
    db.add(snapshot)


async def _build_cloud_price_map() -> dict[str, float]:
    """Build a type-name -> monthly EUR price map from the Cloud API."""
    try:
        types = await hetzner_cloud.list_server_types()
    except Exception:
        logger.debug("Could not fetch server types for pricing")
        return {}

    price_map: dict[str, float] = {}
    for st in types:
        name = st.get("name", "")
        prices = st.get("prices", [])
        for price_entry in prices:
            if price_entry.get("location") == "fsn1":  # Use fsn1 as reference
                try:
                    monthly = float(price_entry.get("price_monthly", {}).get("gross", 0))
                    price_map[name] = monthly
                except (ValueError, TypeError):
                    pass
                break
    return price_map


def _extract_monthly_price(
    server_type_obj: dict[str, Any],
    price_map: dict[str, float],
    type_name: str,
) -> float:
    """Extract monthly cost from the server type object or the price map."""
    # Try inline prices first
    for price_entry in server_type_obj.get("prices", []):
        try:
            return float(
                price_entry.get("price_monthly", {}).get("gross", 0)
            )
        except (ValueError, TypeError):
            continue

    # Fall back to price map
    return price_map.get(type_name, 0.0)


# ---------------------------------------------------------------------------
# Dedicated server collection
# ---------------------------------------------------------------------------

async def collect_dedicated_servers(db: AsyncSession) -> None:
    """Fetch all dedicated servers from the Hetzner Robot API.

    Performs an upsert into the ``Server`` table.  Note that Robot API does
    not provide utilization metrics -- those come from the agent.
    """
    if not settings.hetzner_robot_user:
        logger.debug("Hetzner Robot credentials not configured, skipping")
        return

    logger.info("Collecting dedicated servers from Hetzner Robot API")

    try:
        raw_servers = await hetzner_robot.list_servers()
    except Exception:
        logger.exception("Failed to fetch dedicated servers")
        return

    now = datetime.now(timezone.utc)

    for raw in raw_servers:
        server_ip = raw.get("server_ip", "")
        hetzner_id = str(raw.get("server_number", server_ip))

        result = await db.execute(
            select(Server).where(Server.hetzner_id == hetzner_id)
        )
        server = result.scalar_one_or_none()

        product = raw.get("product", "dedicated")
        datacenter = raw.get("dc", "")

        if server is None:
            server = Server(
                hetzner_id=hetzner_id,
                name=raw.get("server_name", f"dedicated-{hetzner_id}"),
                server_type=product,
                source=ServerSource.dedicated,
                status=raw.get("status", "running"),
                datacenter=datacenter,
                ipv4=server_ip,
                cores=0,
                memory_gb=0.0,
                disk_gb=0,
                monthly_cost_eur=0.0,  # Robot API doesn't expose exact pricing
                labels={},
                created_at=now,
                last_seen_at=now,
            )
            db.add(server)
        else:
            server.name = raw.get("server_name", server.name)
            server.server_type = product
            server.status = raw.get("status", server.status)
            server.datacenter = datacenter
            server.ipv4 = server_ip
            server.last_seen_at = now

    await db.commit()
    logger.info("Dedicated server collection complete (%d servers)", len(raw_servers))


# ---------------------------------------------------------------------------
# Full collection orchestrator
# ---------------------------------------------------------------------------

async def run_collection(db: AsyncSession) -> None:
    """Run the full collection cycle: cloud + dedicated.

    Each sub-collector is wrapped in try/except so a failure in one does not
    prevent the other from running.
    """
    logger.info("Starting collection cycle")

    try:
        await collect_cloud_servers(db)
    except Exception:
        logger.exception("Cloud server collection failed")

    try:
        await collect_dedicated_servers(db)
    except Exception:
        logger.exception("Dedicated server collection failed")

    logger.info("Collection cycle complete")


# ---------------------------------------------------------------------------
# Demo data generator
# ---------------------------------------------------------------------------

# Server definitions for demo mode
_DEMO_SERVERS: list[dict[str, Any]] = [
    {"name": "api-prod", "type": "cx41", "dc": "fsn1-dc14", "project": "main-api", "cpu_base": 45, "cpu_var": 20, "mem_base": 60, "mem_var": 15},
    {"name": "web-prod", "type": "cx31", "dc": "fsn1-dc14", "project": "website", "cpu_base": 25, "cpu_var": 15, "mem_base": 40, "mem_var": 10},
    {"name": "db-master", "type": "cpx41", "dc": "fsn1-dc14", "project": "main-api", "cpu_base": 55, "cpu_var": 25, "mem_base": 75, "mem_var": 10},
    {"name": "staging-1", "type": "cx21", "dc": "nbg1-dc3", "project": "staging", "cpu_base": 3, "cpu_var": 4, "mem_base": 15, "mem_var": 10},
    {"name": "staging-2", "type": "cx21", "dc": "nbg1-dc3", "project": "staging", "cpu_base": 2, "cpu_var": 3, "mem_base": 12, "mem_var": 8},
    {"name": "dev-backend", "type": "cx21", "dc": "nbg1-dc3", "project": "dev", "cpu_base": 4, "cpu_var": 5, "mem_base": 20, "mem_var": 10},
    {"name": "monitoring", "type": "cpx21", "dc": "fsn1-dc14", "project": "infra", "cpu_base": 30, "cpu_var": 10, "mem_base": 50, "mem_var": 10},
    {"name": "ci-runner", "type": "cpx31", "dc": "fsn1-dc14", "project": "infra", "cpu_base": 15, "cpu_var": 60, "mem_base": 35, "mem_var": 30},
    {"name": "old-site", "type": "cx21", "dc": "hel1-dc2", "project": "legacy", "cpu_base": 1, "cpu_var": 1, "mem_base": 8, "mem_var": 3},
    {"name": "cache-prod", "type": "cpx21", "dc": "fsn1-dc14", "project": "main-api", "cpu_base": 20, "cpu_var": 10, "mem_base": 65, "mem_var": 10},
    {"name": "worker-1", "type": "cx31", "dc": "fsn1-dc14", "project": "main-api", "cpu_base": 35, "cpu_var": 20, "mem_base": 45, "mem_var": 15},
    {"name": "analytics", "type": "ax41-nvme", "dc": "fsn1-dc14", "project": "analytics", "cpu_base": 40, "cpu_var": 30, "mem_base": 50, "mem_var": 20},
]

# Approximate prices for demo types
_DEMO_PRICES: dict[str, float] = {
    "cx11": 3.29,
    "cx21": 5.39,
    "cx31": 10.49,
    "cx41": 17.49,
    "cpx11": 3.85,
    "cpx21": 7.19,
    "cpx31": 13.49,
    "cpx41": 24.49,
    "ccx13": 12.49,
    "ccx23": 22.49,
    "ccx33": 42.49,
    "ax41-nvme": 46.41,
}

# Spec map: type -> (cores, memory_gb, disk_gb)
_DEMO_SPECS: dict[str, tuple[int, float, int]] = {
    "cx11": (1, 2.0, 20),
    "cx21": (2, 4.0, 40),
    "cx31": (4, 8.0, 80),
    "cx41": (8, 16.0, 160),
    "cpx11": (2, 2.0, 40),
    "cpx21": (3, 4.0, 80),
    "cpx31": (4, 8.0, 160),
    "cpx41": (8, 16.0, 240),
    "ccx13": (2, 8.0, 80),
    "ccx23": (4, 16.0, 160),
    "ccx33": (8, 32.0, 240),
    "ax41-nvme": (6, 64.0, 512),
}

# Running services to attach to demo servers
_DEMO_SERVICES: dict[str, list[dict[str, Any]]] = {
    "api-prod": [
        {"name": "api-gateway", "type": "docker", "port": 8080, "cpu": 12.0, "mem": 256.0},
        {"name": "api-backend", "type": "docker", "port": 8081, "cpu": 18.0, "mem": 512.0},
        {"name": "nginx", "type": "systemd", "port": 443, "cpu": 2.0, "mem": 64.0},
    ],
    "web-prod": [
        {"name": "frontend-ssr", "type": "docker", "port": 3000, "cpu": 8.0, "mem": 256.0},
        {"name": "nginx", "type": "systemd", "port": 443, "cpu": 1.5, "mem": 48.0},
    ],
    "db-master": [
        {"name": "postgresql", "type": "systemd", "port": 5432, "cpu": 35.0, "mem": 2048.0},
        {"name": "pgbouncer", "type": "docker", "port": 6432, "cpu": 3.0, "mem": 64.0},
    ],
    "staging-1": [
        {"name": "staging-api", "type": "docker", "port": 8080, "cpu": 1.0, "mem": 128.0},
    ],
    "staging-2": [
        {"name": "staging-frontend", "type": "docker", "port": 3000, "cpu": 0.5, "mem": 96.0},
    ],
    "dev-backend": [
        {"name": "dev-api", "type": "docker", "port": 8080, "cpu": 2.0, "mem": 192.0},
        {"name": "dev-db", "type": "docker", "port": 5432, "cpu": 1.0, "mem": 128.0},
    ],
    "monitoring": [
        {"name": "prometheus", "type": "docker", "port": 9090, "cpu": 10.0, "mem": 512.0},
        {"name": "grafana", "type": "docker", "port": 3000, "cpu": 5.0, "mem": 256.0},
        {"name": "alertmanager", "type": "docker", "port": 9093, "cpu": 1.0, "mem": 64.0},
    ],
    "ci-runner": [
        {"name": "gitlab-runner", "type": "docker", "port": None, "cpu": 10.0, "mem": 512.0},
        {"name": "docker-in-docker", "type": "docker", "port": 2376, "cpu": 5.0, "mem": 256.0},
    ],
    "old-site": [
        {"name": "apache2", "type": "systemd", "port": 80, "cpu": 0.3, "mem": 48.0},
        {"name": "mysql", "type": "systemd", "port": 3306, "cpu": 0.5, "mem": 96.0},
    ],
    "cache-prod": [
        {"name": "redis", "type": "docker", "port": 6379, "cpu": 8.0, "mem": 1024.0},
        {"name": "memcached", "type": "docker", "port": 11211, "cpu": 4.0, "mem": 512.0},
    ],
    "worker-1": [
        {"name": "celery-worker", "type": "docker", "port": None, "cpu": 20.0, "mem": 384.0},
        {"name": "celery-beat", "type": "docker", "port": None, "cpu": 2.0, "mem": 64.0},
    ],
    "analytics": [
        {"name": "clickhouse", "type": "docker", "port": 8123, "cpu": 25.0, "mem": 4096.0},
        {"name": "metabase", "type": "docker", "port": 3000, "cpu": 8.0, "mem": 512.0},
    ],
}


async def generate_demo_data(db: AsyncSession) -> None:
    """Seed the database with realistic demo servers and metrics.

    Only runs once -- if any servers already exist, this function returns
    immediately without modifying data.
    """
    result = await db.execute(select(Server.id).limit(1))
    if result.scalar_one_or_none() is not None:
        logger.debug("Demo data already seeded, skipping")
        return

    logger.info("Seeding demo data (%d servers, 30 days of metrics)", len(_DEMO_SERVERS))

    now = datetime.now(timezone.utc)
    rng = random.Random(42)  # Deterministic for reproducible demos

    for idx, spec in enumerate(_DEMO_SERVERS, start=1):
        server_type = spec["type"]
        cores, memory_gb, disk_gb = _DEMO_SPECS.get(
            server_type, (2, 4.0, 40)
        )
        price = _DEMO_PRICES.get(server_type, 5.0)
        source = (
            ServerSource.dedicated
            if server_type.startswith("ax")
            else ServerSource.cloud
        )

        server = Server(
            hetzner_id=f"demo-{idx}",
            name=spec["name"],
            server_type=server_type,
            source=source,
            status="running",
            datacenter=spec["dc"],
            ipv4=f"10.0.{idx // 256}.{idx % 256}",
            cores=cores,
            memory_gb=memory_gb,
            disk_gb=disk_gb,
            monthly_cost_eur=price,
            labels={"env": spec.get("project", ""), "managed-by": "infrascope"},
            project_name=spec.get("project"),
            created_at=now - timedelta(days=90),
            last_seen_at=now,
        )
        db.add(server)
        await db.flush()  # Populate server.id

        # Generate 30 days of hourly metrics (720 data points)
        _generate_metric_snapshots(db, server, spec, now, rng)

        # Attach running services
        _generate_running_services(db, server, now)

    await db.commit()
    logger.info("Demo data seeding complete")


def _generate_metric_snapshots(
    db: AsyncSession,
    server: Server,
    spec: dict[str, Any],
    now: datetime,
    rng: random.Random,
) -> None:
    """Create 30 days of hourly metric snapshots with realistic patterns."""
    cpu_base = spec["cpu_base"]
    cpu_var = spec["cpu_var"]
    mem_base = spec["mem_base"]
    mem_var = spec["mem_var"]

    hours = 30 * 24  # 720 hours

    for h in range(hours):
        ts = now - timedelta(hours=hours - h)
        hour_of_day = ts.hour
        day_of_week = ts.weekday()

        # Simulate daily patterns: higher during business hours (8-18)
        if 8 <= hour_of_day <= 18 and day_of_week < 5:
            time_factor = 1.2
        elif 0 <= hour_of_day <= 5:
            time_factor = 0.6
        else:
            time_factor = 0.9

        # Add sinusoidal variation for organic-looking data
        sin_factor = 1.0 + 0.1 * math.sin(2 * math.pi * h / 24)

        cpu_pct = cpu_base * time_factor * sin_factor + rng.gauss(0, cpu_var * 0.3)
        cpu_pct = max(0.0, min(100.0, cpu_pct))

        mem_pct = mem_base * (0.95 + 0.1 * sin_factor) + rng.gauss(0, mem_var * 0.2)
        mem_pct = max(0.0, min(100.0, mem_pct))

        disk_pct = 30 + 0.02 * h + rng.gauss(0, 1)  # Slowly growing disk
        disk_pct = max(0.0, min(95.0, disk_pct))

        net_in = max(0.0, 2.0 * time_factor + rng.gauss(0, 0.5))
        net_out = max(0.0, 1.5 * time_factor + rng.gauss(0, 0.4))

        load_avg = max(0.0, (cpu_pct / 100.0) * server.cores + rng.gauss(0, 0.3))

        snapshot = MetricSnapshot(
            server_id=server.id,
            timestamp=ts,
            cpu_percent=round(cpu_pct, 2),
            memory_percent=round(mem_pct, 2),
            disk_percent=round(disk_pct, 2),
            network_in_mbps=round(net_in, 2),
            network_out_mbps=round(net_out, 2),
            load_avg_1m=round(load_avg, 2),
        )
        db.add(snapshot)


def _generate_running_services(
    db: AsyncSession,
    server: Server,
    now: datetime,
) -> None:
    """Attach pre-defined running services to a demo server."""
    services = _DEMO_SERVICES.get(server.name, [])

    for svc in services:
        service_type_str = svc["type"]
        try:
            svc_type = ServiceType(service_type_str)
        except ValueError:
            svc_type = ServiceType.docker

        running_svc = RunningService(
            server_id=server.id,
            service_type=svc_type,
            name=svc["name"],
            port=svc.get("port"),
            status="running",
            cpu_percent=svc.get("cpu"),
            memory_mb=svc.get("mem"),
            discovered_at=now - timedelta(days=30),
            last_seen_at=now,
        )
        db.add(running_svc)
