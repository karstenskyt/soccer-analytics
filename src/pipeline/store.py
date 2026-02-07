"""Stage 5: Store session plans in PostgreSQL."""

import json
import logging
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.schemas.session_plan import SessionPlan

logger = logging.getLogger(__name__)


async def store_session_plan(
    session_plan: SessionPlan,
    db: AsyncSession,
) -> UUID:
    """Store a session plan and its drill blocks in PostgreSQL.

    Args:
        session_plan: Validated session plan to store.
        db: Async database session.

    Returns:
        UUID of the stored session plan.
    """
    logger.info(f"Storing session plan: {session_plan.metadata.title}")

    plan_json = session_plan.model_dump(mode="json")
    plan_id = session_plan.id

    await db.execute(
        text("""
            INSERT INTO session_plans (id, title, category, difficulty, author,
                                       source_filename, source_page_count,
                                       extraction_timestamp, raw_json)
            VALUES (:id, :title, :category, :difficulty, :author,
                    :source_filename, :source_page_count,
                    :extraction_timestamp, :raw_json)
            ON CONFLICT (id) DO UPDATE SET
                raw_json = EXCLUDED.raw_json,
                updated_at = NOW()
        """),
        {
            "id": str(plan_id),
            "title": session_plan.metadata.title,
            "category": session_plan.metadata.category,
            "difficulty": session_plan.metadata.difficulty,
            "author": session_plan.metadata.author,
            "source_filename": session_plan.source.filename,
            "source_page_count": session_plan.source.page_count,
            "extraction_timestamp": session_plan.source.extraction_timestamp,
            "raw_json": json.dumps(plan_json),
        },
    )

    for drill in session_plan.drills:
        drill_json = drill.model_dump(mode="json")
        await db.execute(
            text("""
                INSERT INTO drill_blocks (id, session_plan_id, name, setup_description,
                                          player_count, equipment, area_dimensions,
                                          sequence, rules, scoring, coaching_points,
                                          progressions, vlm_description, image_ref, raw_json)
                VALUES (:id, :session_plan_id, :name, :setup_description,
                        :player_count, :equipment, :area_dimensions,
                        :sequence, :rules, :scoring, :coaching_points,
                        :progressions, :vlm_description, :image_ref, :raw_json)
                ON CONFLICT (id) DO UPDATE SET
                    raw_json = EXCLUDED.raw_json
            """),
            {
                "id": str(drill.id),
                "session_plan_id": str(plan_id),
                "name": drill.name,
                "setup_description": drill.setup.description,
                "player_count": drill.setup.player_count,
                "equipment": drill.setup.equipment,
                "area_dimensions": drill.setup.area_dimensions,
                "sequence": drill.sequence,
                "rules": drill.rules,
                "scoring": drill.scoring,
                "coaching_points": drill.coaching_points,
                "progressions": drill.progressions,
                "vlm_description": drill.diagram.vlm_description,
                "image_ref": drill.diagram.image_ref,
                "raw_json": json.dumps(drill_json),
            },
        )

        if drill.tactical_context:
            tc = drill.tactical_context
            await db.execute(
                text("""
                    INSERT INTO tactical_contexts (drill_block_id, methodology,
                                                   game_element, lanes, situation_type)
                    VALUES (:drill_block_id, :methodology, :game_element,
                            :lanes, :situation_type)
                """),
                {
                    "drill_block_id": str(drill.id),
                    "methodology": tc.methodology,
                    "game_element": (
                        tc.game_element.value if tc.game_element else None
                    ),
                    "lanes": (
                        [lane.value for lane in tc.lanes]
                        if tc.lanes
                        else []
                    ),
                    "situation_type": (
                        tc.situation_type.value if tc.situation_type else None
                    ),
                },
            )

    await db.commit()
    logger.info(
        f"Stored session plan {plan_id} with {len(session_plan.drills)} drills"
    )
    return plan_id


async def get_session_plan(
    plan_id: UUID, db: AsyncSession
) -> dict | None:
    """Retrieve a session plan by ID."""
    result = await db.execute(
        text("SELECT raw_json FROM session_plans WHERE id = :id"),
        {"id": str(plan_id)},
    )
    row = result.fetchone()
    if row is None:
        return None
    data = row[0]
    return json.loads(data) if isinstance(data, str) else data


async def list_session_plans(
    db: AsyncSession, limit: int = 50, offset: int = 0
) -> list[dict]:
    """List stored session plans."""
    result = await db.execute(
        text("""
            SELECT id, title, category, difficulty, author,
                   source_filename, extraction_timestamp, created_at
            FROM session_plans
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """),
        {"limit": limit, "offset": offset},
    )
    rows = result.fetchall()
    return [
        {
            "id": str(row[0]),
            "title": row[1],
            "category": row[2],
            "difficulty": row[3],
            "author": row[4],
            "source_filename": row[5],
            "extraction_timestamp": (
                row[6].isoformat() if row[6] else None
            ),
            "created_at": row[7].isoformat() if row[7] else None,
        }
        for row in rows
    ]


async def update_session_plan(
    plan_id: UUID, data: dict, db: AsyncSession
) -> bool:
    """Update a session plan's raw JSON."""
    result = await db.execute(
        text("""
            UPDATE session_plans
            SET raw_json = :raw_json, updated_at = NOW()
            WHERE id = :id
        """),
        {"id": str(plan_id), "raw_json": json.dumps(data)},
    )
    await db.commit()
    return result.rowcount > 0
