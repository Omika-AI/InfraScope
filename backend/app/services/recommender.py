"""Rule-based consolidation recommendation engine.

Generates ``ConsolidationRecommendation`` records by applying a set of
heuristic rules to the current server inventory and their utilization
analysis data.  Designed to run once per day via the scheduler.

Rules implemented:
1. **Idle servers** -- avg CPU < 5 % over 30 days.  Recommend shutdown.
2. **Staging/dev consolidation** -- group staging, dev, and test servers
   and recommend merging them onto a single, right-sized instance.
3. **Right-sizing** -- servers whose peak CPU never exceeds 30 % of their
   current capacity.  Recommend downgrading to the next smaller tier.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Confidence,
    ConsolidationRecommendation,
    RecommendationStatus,
    Server,
)
from app.services.analyzer import analyze_all_servers

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hetzner Cloud approximate pricing (EUR / month)
# ---------------------------------------------------------------------------

PRICE_MAP: dict[str, float] = {
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
}

# Downgrade map: current type -> recommended smaller type
DOWNGRADE_MAP: dict[str, str] = {
    "cx41": "cx31",
    "cx31": "cx21",
    "cx21": "cx11",
    "cpx41": "cpx31",
    "cpx31": "cpx21",
    "cpx21": "cpx11",
    "ccx33": "ccx23",
    "ccx23": "ccx13",
}

# Patterns that indicate staging / dev / test environments
_STAGING_PATTERN = re.compile(r"(staging|dev|test)", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def generate_recommendations(db: AsyncSession) -> list[ConsolidationRecommendation]:
    """Run all recommendation rules and persist the results.

    Existing **pending** recommendations are cleared before inserting new
    ones so that the recommendation list always reflects the latest analysis.
    Accepted and dismissed recommendations are left intact.

    Returns:
        The list of newly created ``ConsolidationRecommendation`` records.
    """
    logger.info("Generating consolidation recommendations")

    # Fetch analysis data and servers
    analyses = await analyze_all_servers(db)
    analysis_by_id: dict[int, dict[str, Any]] = {
        a["server_id"]: a for a in analyses
    }

    result = await db.execute(select(Server))
    servers: list[Server] = list(result.scalars().all())
    server_by_id: dict[int, Server] = {s.id: s for s in servers}

    # Clear stale pending recommendations
    await db.execute(
        delete(ConsolidationRecommendation).where(
            ConsolidationRecommendation.status == RecommendationStatus.pending
        )
    )

    new_recs: list[ConsolidationRecommendation] = []

    # Rule 1: Idle servers
    new_recs.extend(
        _find_idle_servers(server_by_id, analysis_by_id)
    )

    # Rule 2: Staging / dev consolidation
    new_recs.extend(
        _find_staging_consolidation(server_by_id, analysis_by_id)
    )

    # Rule 3: Right-sizing
    new_recs.extend(
        _find_rightsizing_candidates(server_by_id, analysis_by_id)
    )

    for rec in new_recs:
        db.add(rec)

    await db.commit()

    logger.info("Created %d new recommendations", len(new_recs))
    return new_recs


# ---------------------------------------------------------------------------
# Rule implementations
# ---------------------------------------------------------------------------

def _find_idle_servers(
    server_by_id: dict[int, Server],
    analysis_by_id: dict[int, dict[str, Any]],
) -> list[ConsolidationRecommendation]:
    """Rule 1: Recommend shutting down servers with < 5 % avg CPU."""
    recs: list[ConsolidationRecommendation] = []

    for sid, analysis in analysis_by_id.items():
        if analysis["utilization_tier"] != "idle":
            continue

        server = server_by_id.get(sid)
        if server is None:
            continue

        # Skip servers that are already stopped
        if server.status != "running":
            continue

        monthly_cost = server.monthly_cost_eur
        if monthly_cost <= 0:
            continue

        # Pick the smallest downgrade available, or suggest consolidation
        current_type = server.server_type.lower()
        smaller_type = DOWNGRADE_MAP.get(current_type)
        if smaller_type:
            target_cost = PRICE_MAP.get(smaller_type, 0.0)
            savings = monthly_cost - target_cost
            target_label = smaller_type
            action_text = (
                f"This server is barely using its resources — averaging just "
                f"{analysis['avg_cpu_30d']:.1f}% CPU over 30 days (peak "
                f"{analysis['peak_cpu_30d']:.1f}%). Downgrading from "
                f"{server.server_type} to {smaller_type} would save "
                f"EUR {savings:.2f}/mo. Alternatively, its workloads could "
                f"be consolidated onto another server to free up this instance entirely."
            )
        else:
            target_cost = 0.0
            savings = monthly_cost
            target_label = "downsize / consolidate"
            action_text = (
                f"This server is barely using its resources — averaging just "
                f"{analysis['avg_cpu_30d']:.1f}% CPU over 30 days (peak "
                f"{analysis['peak_cpu_30d']:.1f}%). Its workloads could likely "
                f"be consolidated onto another server, saving the full "
                f"EUR {monthly_cost:.2f}/mo. Review what's running on it "
                f"to decide the best path."
            )

        rec = ConsolidationRecommendation(
            group_name=f"Underutilized: {server.name}",
            server_ids=[server.id],
            target_server_type=target_label,
            current_total_cost_eur=monthly_cost,
            projected_cost_eur=target_cost,
            monthly_savings_eur=savings,
            rationale=action_text,
            confidence=Confidence.high,
            status=RecommendationStatus.pending,
            created_at=datetime.now(timezone.utc),
        )
        recs.append(rec)

    return recs


def _find_staging_consolidation(
    server_by_id: dict[int, Server],
    analysis_by_id: dict[int, dict[str, Any]],
) -> list[ConsolidationRecommendation]:
    """Rule 2: Merge staging/dev/test servers onto one instance."""
    staging_servers: list[Server] = []

    for server in server_by_id.values():
        if server.status != "running":
            continue
        name_match = _STAGING_PATTERN.search(server.name or "")
        project_match = _STAGING_PATTERN.search(server.project_name or "")
        label_match = any(
            _STAGING_PATTERN.search(str(v))
            for v in (server.labels or {}).values()
        )
        if name_match or project_match or label_match:
            staging_servers.append(server)

    # Only recommend consolidation if there are at least 2 staging servers
    if len(staging_servers) < 2:
        return []

    total_cost = sum(s.monthly_cost_eur for s in staging_servers)
    server_ids = [s.id for s in staging_servers]

    # Find the combined peak CPU to pick a target type
    combined_peak_cpu = sum(
        analysis_by_id.get(s.id, {}).get("peak_cpu_30d", 0.0)
        for s in staging_servers
    )

    # Pick the smallest server type whose capacity can handle the combined load
    # (assuming peak doesn't exceed 70% of the target)
    target_type = _pick_target_type_for_combined_load(
        combined_peak_cpu, staging_servers
    )
    target_cost = PRICE_MAP.get(target_type, total_cost * 0.5)
    savings = max(total_cost - target_cost, 0.0)

    if savings <= 0:
        return []

    server_names = ", ".join(s.name for s in staging_servers)
    rec = ConsolidationRecommendation(
        group_name="Staging/dev server consolidation",
        server_ids=server_ids,
        target_server_type=target_type,
        current_total_cost_eur=round(total_cost, 2),
        projected_cost_eur=round(target_cost, 2),
        monthly_savings_eur=round(savings, 2),
        rationale=(
            f"These non-production servers ({server_names}) cost a combined "
            f"EUR {total_cost:.2f}/mo but their total peak CPU is only "
            f"{combined_peak_cpu:.1f}%. They could share a single "
            f"{target_type} (EUR {target_cost:.2f}/mo) with room to spare, "
            f"saving EUR {savings:.2f}/mo."
        ),
        confidence=Confidence.medium,
        status=RecommendationStatus.pending,
        created_at=datetime.now(timezone.utc),
    )
    return [rec]


def _find_rightsizing_candidates(
    server_by_id: dict[int, Server],
    analysis_by_id: dict[int, dict[str, Any]],
) -> list[ConsolidationRecommendation]:
    """Rule 3: Downgrade servers whose peak CPU stays below 30 %."""
    recs: list[ConsolidationRecommendation] = []

    for sid, analysis in analysis_by_id.items():
        peak_cpu = analysis.get("peak_cpu_30d", 100.0)
        if peak_cpu >= 30:
            continue

        # Already covered by the idle rule
        if analysis["utilization_tier"] == "idle":
            continue

        server = server_by_id.get(sid)
        if server is None or server.status != "running":
            continue

        current_type = server.server_type.lower()
        smaller_type = DOWNGRADE_MAP.get(current_type)
        if smaller_type is None:
            # Already the smallest tier or not in the map
            continue

        current_cost = server.monthly_cost_eur
        if current_cost <= 0:
            current_cost = PRICE_MAP.get(current_type, 0.0)

        target_cost = PRICE_MAP.get(smaller_type, current_cost)
        savings = current_cost - target_cost

        if savings <= 0:
            continue

        rec = ConsolidationRecommendation(
            group_name=f"Right-size: {server.name}",
            server_ids=[server.id],
            target_server_type=smaller_type,
            current_total_cost_eur=round(current_cost, 2),
            projected_cost_eur=round(target_cost, 2),
            monthly_savings_eur=round(savings, 2),
            rationale=(
                f"'{server.name}' peaks at only {peak_cpu:.1f}% CPU "
                f"(avg {analysis['avg_cpu_30d']:.1f}%) on a {current_type}. "
                f"A {smaller_type} can comfortably handle this workload "
                f"and would save EUR {savings:.2f}/mo while still leaving "
                f"plenty of headroom for traffic spikes."
            ),
            confidence=Confidence.medium,
            status=RecommendationStatus.pending,
            created_at=datetime.now(timezone.utc),
        )
        recs.append(rec)

    return recs


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _pick_target_type_for_combined_load(
    combined_peak_cpu: float,
    servers: list[Server],
) -> str:
    """Choose the smallest Hetzner type that can handle the combined load.

    We target keeping peak utilization at or below 70 % of the new server's
    capacity.  As a simplification, we use the cx/cpx families sorted by
    price and pick the cheapest one whose cores can accommodate the load.
    """
    # Estimate total cores needed: combined_peak_cpu as a fraction of the
    # sum of original cores, then require headroom to stay under 70%.
    total_original_cores = sum(s.cores for s in servers) or 1
    effective_cores_needed = (combined_peak_cpu / 100.0) * total_original_cores
    target_cores = max(effective_cores_needed / 0.7, 1.0)

    # Simplified core count per type
    type_cores: dict[str, int] = {
        "cx11": 1,
        "cx21": 2,
        "cx31": 4,
        "cx41": 8,
        "cpx11": 2,
        "cpx21": 3,
        "cpx31": 4,
        "cpx41": 8,
        "ccx13": 2,
        "ccx23": 4,
        "ccx33": 8,
    }

    # Sort candidates by price ascending
    candidates = sorted(PRICE_MAP.items(), key=lambda x: x[1])

    for type_name, _price in candidates:
        cores = type_cores.get(type_name, 1)
        if cores >= target_cores:
            return type_name

    # Fallback: biggest type
    return candidates[-1][0] if candidates else "cx41"
