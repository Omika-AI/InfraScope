"""Cost overview and history API routes."""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import ConsolidationRecommendation, RecommendationStatus, Server, ServerSource
from app.schemas import CostBreakdown, CostHistoryPoint, CostOverview

router = APIRouter(prefix="/costs", tags=["Costs"])

# ── Cost Overview ────────────────────────────────────────


@router.get("/overview", response_model=CostOverview)
async def cost_overview(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CostOverview:
    """Aggregate all server costs with breakdowns by source, datacenter, and project."""
    # Total cost and server count
    totals_stmt = select(
        func.coalesce(func.sum(Server.monthly_cost_eur), 0.0),
        func.count(Server.id),
    )
    totals_result = await db.execute(totals_stmt)
    total_row = totals_result.one()
    total_monthly_eur: float = float(total_row[0])
    server_count: int = total_row[1]

    # Cloud vs dedicated breakdown
    source_stmt = select(
        Server.source,
        func.coalesce(func.sum(Server.monthly_cost_eur), 0.0),
    ).group_by(Server.source)
    source_result = await db.execute(source_stmt)
    source_rows = source_result.all()

    cloud_cost = 0.0
    dedicated_cost = 0.0
    for source, cost in source_rows:
        if source == ServerSource.cloud:
            cloud_cost = float(cost)
        elif source == ServerSource.dedicated:
            dedicated_cost = float(cost)

    # By datacenter
    dc_stmt = select(
        Server.datacenter,
        func.coalesce(func.sum(Server.monthly_cost_eur), 0.0),
        func.count(Server.id),
    ).group_by(Server.datacenter)
    dc_result = await db.execute(dc_stmt)
    by_datacenter = [
        CostBreakdown(category=dc or "unknown", cost_eur=round(float(cost), 2), count=cnt)
        for dc, cost, cnt in dc_result.all()
    ]

    # By project
    project_stmt = select(
        Server.project_name,
        func.coalesce(func.sum(Server.monthly_cost_eur), 0.0),
        func.count(Server.id),
    ).group_by(Server.project_name)
    project_result = await db.execute(project_stmt)
    by_project = [
        CostBreakdown(
            category=project or "unassigned",
            cost_eur=round(float(cost), 2),
            count=cnt,
        )
        for project, cost, cnt in project_result.all()
    ]

    # Potential savings from pending recommendations
    savings_stmt = select(
        func.coalesce(func.sum(ConsolidationRecommendation.monthly_savings_eur), 0.0)
    ).where(ConsolidationRecommendation.status == RecommendationStatus.pending)
    savings_result = await db.execute(savings_stmt)
    potential_savings_eur: float = float(savings_result.scalar_one())

    return CostOverview(
        total_monthly_eur=round(total_monthly_eur, 2),
        cloud_cost_eur=round(cloud_cost, 2),
        dedicated_cost_eur=round(dedicated_cost, 2),
        potential_savings_eur=round(potential_savings_eur, 2),
        server_count=server_count,
        by_datacenter=sorted(by_datacenter, key=lambda b: b.cost_eur, reverse=True),
        by_project=sorted(by_project, key=lambda b: b.cost_eur, reverse=True),
    )


# ── Cost History ─────────────────────────────────────────


@router.get("/history", response_model=list[CostHistoryPoint])
async def cost_history(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[CostHistoryPoint]:
    """Generate monthly cost history for the last 12 months.

    Since we may not have 12 months of real historical data, this uses the
    current server inventory costs as a baseline and projects backwards.
    Servers that were created within the last 12 months only contribute to
    months after their creation date.
    """
    now = datetime.now(timezone.utc)

    # Fetch all servers with their costs and creation dates
    result = await db.execute(
        select(Server.source, Server.monthly_cost_eur, Server.created_at)
    )
    servers = result.all()

    # Build 12 months of history
    history: list[CostHistoryPoint] = []

    for months_ago in range(11, -1, -1):
        # Calculate the month for this data point
        year = now.year
        month = now.month - months_ago
        while month <= 0:
            month += 12
            year -= 1

        month_label = f"{year}-{month:02d}"
        month_start = datetime(year, month, 1, tzinfo=timezone.utc)

        cloud_eur = 0.0
        dedicated_eur = 0.0

        for source, cost, created_at in servers:
            # Only include servers that existed in this month
            if created_at is not None and created_at > month_start:
                continue

            if source == ServerSource.cloud:
                cloud_eur += cost
            else:
                dedicated_eur += cost

        history.append(
            CostHistoryPoint(
                month=month_label,
                total_eur=round(cloud_eur + dedicated_eur, 2),
                cloud_eur=round(cloud_eur, 2),
                dedicated_eur=round(dedicated_eur, 2),
            )
        )

    return history
