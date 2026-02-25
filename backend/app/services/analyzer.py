"""Utilization analysis service.

Processes stored ``MetricSnapshot`` records to compute aggregate statistics
(30-day averages and peaks) for each server, and classifies servers into
utilization tiers that drive the consolidation recommendation engine.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MetricSnapshot, Server

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Utilization tier classification
# ---------------------------------------------------------------------------

def classify_utilization(avg_cpu_30d: float) -> str:
    """Classify a server's utilization tier based on its 30-day average CPU.

    Returns:
        One of ``"idle"``, ``"low"``, ``"moderate"``, ``"high"``, or
        ``"critical"``.
    """
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


# ---------------------------------------------------------------------------
# Per-server analysis
# ---------------------------------------------------------------------------

async def analyze_server(
    db: AsyncSession,
    server_id: int,
) -> dict[str, Any] | None:
    """Compute 30-day utilization statistics for a single server.

    Args:
        db: Active database session.
        server_id: Primary key of the ``Server`` row.

    Returns:
        A dict with keys ``server_id``, ``avg_cpu_30d``, ``avg_memory_30d``,
        ``peak_cpu_30d``, ``peak_memory_30d``, and ``utilization_tier``.
        Returns ``None`` if the server has no metrics in the window.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    stmt = (
        select(
            func.avg(MetricSnapshot.cpu_percent).label("avg_cpu"),
            func.avg(MetricSnapshot.memory_percent).label("avg_memory"),
            func.max(MetricSnapshot.cpu_percent).label("peak_cpu"),
            func.max(MetricSnapshot.memory_percent).label("peak_memory"),
        )
        .where(MetricSnapshot.server_id == server_id)
        .where(MetricSnapshot.timestamp >= cutoff)
    )

    result = await db.execute(stmt)
    row = result.one_or_none()

    if row is None or row.avg_cpu is None:
        return None

    avg_cpu = round(float(row.avg_cpu), 2)
    avg_memory = round(float(row.avg_memory), 2)
    peak_cpu = round(float(row.peak_cpu), 2)
    peak_memory = round(float(row.peak_memory), 2)

    return {
        "server_id": server_id,
        "avg_cpu_30d": avg_cpu,
        "avg_memory_30d": avg_memory,
        "peak_cpu_30d": peak_cpu,
        "peak_memory_30d": peak_memory,
        "utilization_tier": classify_utilization(avg_cpu),
    }


# ---------------------------------------------------------------------------
# Bulk analysis
# ---------------------------------------------------------------------------

async def analyze_all_servers(
    db: AsyncSession,
) -> list[dict[str, Any]]:
    """Run ``analyze_server`` for every server in the database.

    Returns:
        A list of analysis dicts.  Servers that have no metric data in the
        last 30 days are included with zeroed values and tier ``"idle"``.
    """
    stmt = select(Server.id)
    result = await db.execute(stmt)
    server_ids: list[int] = [row[0] for row in result.all()]

    analyses: list[dict[str, Any]] = []

    for sid in server_ids:
        analysis = await analyze_server(db, sid)
        if analysis is not None:
            analyses.append(analysis)
        else:
            # Server exists but has no metrics -- treat as idle/unknown
            analyses.append(
                {
                    "server_id": sid,
                    "avg_cpu_30d": 0.0,
                    "avg_memory_30d": 0.0,
                    "peak_cpu_30d": 0.0,
                    "peak_memory_30d": 0.0,
                    "utilization_tier": "idle",
                }
            )

    logger.info(
        "Analyzed %d servers: %s",
        len(analyses),
        _tier_summary(analyses),
    )
    return analyses


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tier_summary(analyses: list[dict[str, Any]]) -> str:
    """Build a compact summary string of tier counts for logging."""
    counts: dict[str, int] = {}
    for a in analyses:
        tier = a["utilization_tier"]
        counts[tier] = counts.get(tier, 0) + 1
    return ", ".join(f"{tier}={count}" for tier, count in sorted(counts.items()))
