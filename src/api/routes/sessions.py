"""Session plan CRUD endpoints."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db
from src.pipeline.store import (
    get_session_plan,
    list_session_plans,
    update_session_plan,
)

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
    data: dict,
    db: AsyncSession = Depends(get_db),
):
    """Update a session plan."""
    updated = await update_session_plan(plan_id, data, db)
    if not updated:
        raise HTTPException(
            status_code=404, detail="Session plan not found"
        )
    return {"status": "updated", "plan_id": str(plan_id)}
