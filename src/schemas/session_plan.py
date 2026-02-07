"""Pydantic models for soccer session plan extraction."""

from datetime import UTC, datetime
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from .tactical import TacticalContext


class PlayerPosition(BaseModel):
    """Position of a player on the pitch diagram."""

    label: str = Field(..., description="Player label (e.g., 'GK', 'A1', 'D1')")
    x: float = Field(..., description="X coordinate (0-100, left to right)")
    y: float = Field(..., description="Y coordinate (0-100, bottom to top)")
    role: Optional[str] = Field(
        None, description="Role description (e.g., 'goalkeeper', 'attacker')"
    )


class DiagramInfo(BaseModel):
    """Information extracted from a drill diagram by the VLM."""

    image_ref: Optional[str] = Field(
        None, description="Path to extracted diagram image"
    )
    vlm_description: str = Field(
        "", description="VLM-generated description of the diagram"
    )
    player_positions: list[PlayerPosition] = Field(
        default_factory=list, description="Player positions extracted from diagram"
    )
    movement_arrows: Optional[str] = Field(
        None, description="Description of movement patterns shown"
    )


class DrillSetup(BaseModel):
    """Setup information for a drill block."""

    description: str = Field("", description="Setup description text")
    player_count: Optional[str] = Field(
        None,
        description="Number/description of players (e.g., '1 GK + 6 field players')",
    )
    equipment: list[str] = Field(
        default_factory=list, description="Required equipment"
    )
    area_dimensions: Optional[str] = Field(
        None, description="Playing area dimensions (e.g., '20x15 yards')"
    )


class DrillBlock(BaseModel):
    """A single drill/exercise within a session plan."""

    id: UUID = Field(default_factory=uuid4)
    name: str = Field(..., description="Drill name (e.g., 'Coach-Goalkeeper(s)')")
    setup: DrillSetup = Field(default_factory=DrillSetup)
    diagram: DiagramInfo = Field(default_factory=DiagramInfo)
    sequence: list[str] = Field(
        default_factory=list, description="Numbered execution steps"
    )
    rules: list[str] = Field(
        default_factory=list, description="Rules and constraints"
    )
    scoring: list[str] = Field(
        default_factory=list, description="Scoring criteria"
    )
    coaching_points: list[str] = Field(
        default_factory=list, description="Key coaching observations"
    )
    progressions: list[str] = Field(
        default_factory=list, description="Progression variations"
    )
    tactical_context: Optional[TacticalContext] = Field(
        None, description="Tactical methodology context"
    )


class SessionMetadata(BaseModel):
    """Metadata about a session plan."""

    title: str = Field(..., description="Session plan title")
    category: Optional[str] = Field(
        None, description="Category (e.g., 'Goalkeeping: General')"
    )
    difficulty: Optional[str] = Field(
        None, description="Difficulty level (e.g., 'Moderate')"
    )
    author: Optional[str] = Field(None, description="Author or organization")
    target_age_group: Optional[str] = Field(None, description="Target age group")
    duration_minutes: Optional[int] = Field(
        None, description="Session duration in minutes"
    )


class Source(BaseModel):
    """Source document information."""

    filename: str = Field(..., description="Original PDF filename")
    page_count: int = Field(0, description="Number of pages in source PDF")
    extraction_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC)
    )


class SessionPlan(BaseModel):
    """Complete extracted session plan."""

    id: UUID = Field(default_factory=uuid4)
    metadata: SessionMetadata
    drills: list[DrillBlock] = Field(
        default_factory=list, description="Drill blocks in order"
    )
    source: Source
