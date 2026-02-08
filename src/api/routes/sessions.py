"""Session plan CRUD endpoints."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db
from src.pipeline.store import (
    get_session_plan,
    list_session_plans,
    replace_session_plan,
)
from src.pipeline.validate import validate_and_enrich
from src.rendering.pdf_report import generate_session_pdf
from src.schemas.session_plan import SessionPlan

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("")
async def list_sessions(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List all stored session plans."""
    sessions = await list_session_plans(db, limit=limit, offset=offset)
    return {"sessions": sessions, "count": len(sessions)}


@router.get("/{plan_id}")
async def get_session(
    plan_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific session plan by ID."""
    plan = await get_session_plan(plan_id, db)
    if plan is None:
        raise HTTPException(
            status_code=404, detail="Session plan not found"
        )
    return plan


@router.put("/{plan_id}")
async def update_session(
    plan_id: UUID,
    body: SessionPlan,
    db: AsyncSession = Depends(get_db),
):
    """Update a session plan with validated data and tactical re-enrichment."""
    # Ensure the body ID matches the URL
    body.id = plan_id

    # Check that the plan exists
    existing = await get_session_plan(plan_id, db)
    if existing is None:
        raise HTTPException(
            status_code=404, detail="Session plan not found"
        )

    # Re-enrich with tactical context
    enriched = await validate_and_enrich(body)

    # Replace in database
    await replace_session_plan(plan_id, enriched, db)

    return enriched.model_dump(mode="json")


@router.get("/{plan_id}/export")
async def export_session(
    plan_id: UUID,
    format: str = Query(default="pdf", pattern="^pdf$"),
    db: AsyncSession = Depends(get_db),
):
    """Export a session plan as a professional coaching PDF."""
    raw = await get_session_plan(plan_id, db)
    if raw is None:
        raise HTTPException(
            status_code=404, detail="Session plan not found"
        )

    plan = SessionPlan.model_validate(raw)
    pdf_bytes = generate_session_pdf(plan)

    filename = f"{plan.metadata.title.replace(' ', '_')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
