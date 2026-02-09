"""Semantic search endpoint for soccer drills."""

import logging
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_colpali_client, get_db
from src.pipeline.store import get_session_plan

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["search"])


@router.get("/search")
async def search_drills(
    q: str = Query(..., min_length=1, description="Search query"),
    k: int = Query(5, ge=1, le=50, description="Number of results"),
    db: AsyncSession = Depends(get_db),
    colpali_client: httpx.AsyncClient | None = Depends(get_colpali_client),
):
    """Search indexed drills using visual semantic retrieval.

    Uses ColPali/byaldi to find drills matching natural language queries
    like "counter attack 2v1 drills" or "goalkeeper training exercises".
    """
    if colpali_client is None:
        raise HTTPException(
            status_code=503,
            detail="Visual search is not configured (COLPALI_URL not set)",
        )

    try:
        resp = await colpali_client.post(
            "/search",
            json={"query": q, "k": k},
        )
        resp.raise_for_status()
    except httpx.ConnectError:
        raise HTTPException(
            status_code=502,
            detail="ColPali service is unavailable",
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=f"ColPali service error: {e.response.status_code}",
        )

    search_data = resp.json()
    results = search_data.get("results", [])

    enriched = []
    seen_plans: dict[str, dict | None] = {}

    for hit in results:
        plan_id = hit.get("plan_id")
        if plan_id and plan_id not in seen_plans:
            try:
                seen_plans[plan_id] = await get_session_plan(
                    UUID(plan_id), db
                )
            except Exception:
                logger.warning("Failed to fetch plan %s for search enrichment", plan_id, exc_info=True)
                seen_plans[plan_id] = None

        plan_data = seen_plans.get(plan_id) if plan_id else None
        entry = {
            "score": hit.get("score", 0.0),
            "page_num": hit.get("page_num", 0),
            "plan_id": plan_id,
            "filename": hit.get("filename"),
        }

        if plan_data:
            metadata = plan_data.get("metadata", {})
            entry["plan_title"] = metadata.get("title")
            entry["category"] = metadata.get("category")
            drills = plan_data.get("drills", [])
            entry["drill_names"] = [d.get("name", "") for d in drills]

        enriched.append(entry)

    return {
        "query": q,
        "results": enriched,
        "total": len(enriched),
    }
