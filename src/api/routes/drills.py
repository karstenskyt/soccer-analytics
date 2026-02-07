"""Drill-level endpoints with pitch diagram rendering."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db
from src.pipeline.store import get_session_plan
from src.rendering.pitch import render_drill_diagram
from src.schemas.session_plan import DrillBlock, SessionPlan

logger = logging.getLogger(__name__)

router = APIRouter(tags=["drills"])


def _get_plan_and_drill(raw: dict, plan_id: UUID, drill_index: int) -> tuple[SessionPlan, DrillBlock]:
    """Parse raw JSON into SessionPlan and extract a drill by index."""
    plan = SessionPlan.model_validate(raw)
    if drill_index < 0 or drill_index >= len(plan.drills):
        raise HTTPException(
            status_code=404,
            detail=f"Drill index {drill_index} out of range (plan has {len(plan.drills)} drills)",
        )
    return plan, plan.drills[drill_index]


@router.get("/api/sessions/{plan_id}/drills")
async def list_drills(
    plan_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """List drills for a session plan."""
    raw = await get_session_plan(plan_id, db)
    if raw is None:
        raise HTTPException(status_code=404, detail="Session plan not found")

    plan = SessionPlan.model_validate(raw)
    return {
        "plan_id": str(plan_id),
        "drills": [
            {
                "index": i,
                "id": str(drill.id),
                "name": drill.name,
                "has_positions": len(drill.diagram.player_positions) > 0,
            }
            for i, drill in enumerate(plan.drills)
        ],
    }


@router.get("/api/sessions/{plan_id}/drills/{drill_index}")
async def get_drill(
    plan_id: UUID,
    drill_index: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific drill by index."""
    raw = await get_session_plan(plan_id, db)
    if raw is None:
        raise HTTPException(status_code=404, detail="Session plan not found")

    _, drill = _get_plan_and_drill(raw, plan_id, drill_index)
    return drill.model_dump(mode="json")


@router.get("/api/sessions/{plan_id}/drills/{drill_index}/diagram")
async def get_drill_diagram(
    plan_id: UUID,
    drill_index: int,
    fmt: str = "png",
    db: AsyncSession = Depends(get_db),
):
    """Render a pitch diagram for a specific drill."""
    if fmt not in ("png", "pdf"):
        raise HTTPException(status_code=400, detail="Format must be 'png' or 'pdf'")

    raw = await get_session_plan(plan_id, db)
    if raw is None:
        raise HTTPException(status_code=404, detail="Session plan not found")

    _, drill = _get_plan_and_drill(raw, plan_id, drill_index)
    image_bytes = render_drill_diagram(drill, fmt=fmt)

    media_type = "image/png" if fmt == "png" else "application/pdf"
    return Response(content=image_bytes, media_type=media_type)


@router.post("/api/render")
async def render_adhoc(drill: DrillBlock, fmt: str = "png"):
    """Render a pitch diagram from an ad-hoc DrillBlock JSON body."""
    if fmt not in ("png", "pdf"):
        raise HTTPException(status_code=400, detail="Format must be 'png' or 'pdf'")

    image_bytes = render_drill_diagram(drill, fmt=fmt)
    media_type = "image/png" if fmt == "png" else "application/pdf"
    return Response(content=image_bytes, media_type=media_type)
