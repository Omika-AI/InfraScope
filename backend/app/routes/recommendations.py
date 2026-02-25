"""Consolidation recommendation API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import ConsolidationRecommendation, RecommendationStatus
from app.schemas import RecommendationItem

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])

# ── List Recommendations ─────────────────────────────────


@router.get("", response_model=list[RecommendationItem])
async def list_recommendations(
    db: Annotated[AsyncSession, Depends(get_db)],
    status: Annotated[
        str | None,
        Query(description="Filter by status: pending, accepted, or dismissed"),
    ] = None,
) -> list[RecommendationItem]:
    """List consolidation recommendations, optionally filtered by status."""
    stmt = select(ConsolidationRecommendation)

    if status is not None:
        # Validate the status value
        try:
            status_enum = RecommendationStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status '{status}'. Must be one of: pending, accepted, dismissed",
            )
        stmt = stmt.where(ConsolidationRecommendation.status == status_enum)

    stmt = stmt.order_by(ConsolidationRecommendation.monthly_savings_eur.desc())

    result = await db.execute(stmt)
    recommendations = result.scalars().all()

    return [RecommendationItem.model_validate(rec) for rec in recommendations]


# ── Dismiss Recommendation ───────────────────────────────


@router.post("/{rec_id}/dismiss", response_model=RecommendationItem)
async def dismiss_recommendation(
    rec_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RecommendationItem:
    """Dismiss a consolidation recommendation."""
    stmt = select(ConsolidationRecommendation).where(
        ConsolidationRecommendation.id == rec_id
    )
    result = await db.execute(stmt)
    rec = result.scalar_one_or_none()

    if rec is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    rec.status = RecommendationStatus.dismissed
    await db.commit()
    await db.refresh(rec)

    return RecommendationItem.model_validate(rec)


# ── Accept Recommendation ────────────────────────────────


@router.post("/{rec_id}/accept", response_model=RecommendationItem)
async def accept_recommendation(
    rec_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RecommendationItem:
    """Accept a consolidation recommendation for tracking."""
    stmt = select(ConsolidationRecommendation).where(
        ConsolidationRecommendation.id == rec_id
    )
    result = await db.execute(stmt)
    rec = result.scalar_one_or_none()

    if rec is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    rec.status = RecommendationStatus.accepted
    await db.commit()
    await db.refresh(rec)

    return RecommendationItem.model_validate(rec)
