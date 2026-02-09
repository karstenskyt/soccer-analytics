"""Pydantic models for soccer session plan extraction."""

from datetime import UTC, datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from .tactical import TacticalContext


# --- Enriched diagram enums ---


class PitchViewType(str, Enum):
    """What portion of the pitch is shown in the diagram."""

    FULL_PITCH = "full_pitch"
    HALF_PITCH = "half_pitch"
    PENALTY_AREA = "penalty_area"
    THIRD = "third"
    CUSTOM = "custom"


class ArrowType(str, Enum):
    """Classification of movement arrows in diagrams."""

    RUN = "run"
    PASS = "pass"
    SHOT = "shot"
    DRIBBLE = "dribble"
    CROSS = "cross"
    THROUGH_BALL = "through_ball"
    MOVEMENT = "movement"


class EquipmentType(str, Enum):
    """Types of training equipment shown in diagrams."""

    CONE = "cone"
    MANNEQUIN = "mannequin"
    POLE = "pole"
    GATE = "gate"
    HURDLE = "hurdle"
    MINI_GOAL = "mini_goal"
    FULL_GOAL = "full_goal"
    FLAG = "flag"


# --- Enriched diagram models ---


class PitchView(BaseModel):
    """Pitch dimensions and view type for the diagram."""

    view_type: PitchViewType = Field(
        PitchViewType.HALF_PITCH, description="What part of pitch is shown"
    )
    length_meters: Optional[float] = Field(
        None, description="Length of visible area in meters"
    )
    width_meters: Optional[float] = Field(
        None, description="Width of visible area in meters"
    )
    orientation: str = Field(
        "vertical", description="Orientation: 'vertical' or 'horizontal'"
    )


class MovementArrow(BaseModel):
    """A structured movement arrow on the diagram."""

    start_x: float = Field(..., description="Start X coordinate (0-100)")
    start_y: float = Field(..., description="Start Y coordinate (0-100)")
    end_x: float = Field(..., description="End X coordinate (0-100)")
    end_y: float = Field(..., description="End Y coordinate (0-100)")
    arrow_type: ArrowType = Field(
        ArrowType.MOVEMENT, description="Type of movement"
    )
    from_label: Optional[str] = Field(
        None, description="Label of the player/object at arrow start"
    )
    to_label: Optional[str] = Field(
        None, description="Label of the player/object at arrow end"
    )
    sequence_number: Optional[int] = Field(
        None, description="Order in the drill sequence"
    )
    label: Optional[str] = Field(
        None, description="Text label on the arrow"
    )


class EquipmentObject(BaseModel):
    """A piece of equipment placed on the diagram."""

    equipment_type: EquipmentType = Field(
        ..., description="Type of equipment"
    )
    x: float = Field(..., description="X coordinate (0-100)")
    y: float = Field(..., description="Y coordinate (0-100)")
    x2: Optional[float] = Field(
        None, description="End X for gates/lines (0-100)"
    )
    y2: Optional[float] = Field(
        None, description="End Y for gates/lines (0-100)"
    )
    label: Optional[str] = Field(None, description="Text label")
    color: Optional[str] = Field(None, description="Color of equipment")


class GoalInfo(BaseModel):
    """A goal on the diagram."""

    x: float = Field(..., description="X center coordinate (0-100)")
    y: float = Field(..., description="Y center coordinate (0-100)")
    goal_type: str = Field(
        "full_goal", description="'full_goal', 'mini_goal', or 'target_goal'"
    )
    width_meters: Optional[float] = Field(
        None, description="Goal width in meters"
    )


class BallPosition(BaseModel):
    """A ball position on the diagram."""

    x: float = Field(..., description="X coordinate (0-100)")
    y: float = Field(..., description="Y coordinate (0-100)")
    label: Optional[str] = Field(None, description="Text label")


class PitchZone(BaseModel):
    """A marked zone or area on the diagram."""

    zone_type: str = Field(
        "area", description="Zone type (e.g., 'area', 'channel', 'box')"
    )
    x1: float = Field(..., description="Top-left X coordinate (0-100)")
    y1: float = Field(..., description="Top-left Y coordinate (0-100)")
    x2: float = Field(..., description="Bottom-right X coordinate (0-100)")
    y2: float = Field(..., description="Bottom-right Y coordinate (0-100)")
    label: Optional[str] = Field(None, description="Zone label")
    color: Optional[str] = Field(None, description="Zone color")


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
    pitch_view: Optional[PitchView] = Field(
        None, description="Pitch view type and dimensions"
    )
    arrows: list[MovementArrow] = Field(
        default_factory=list, description="Structured movement arrows"
    )
    equipment: list[EquipmentObject] = Field(
        default_factory=list, description="Equipment objects on the diagram"
    )
    goals: list[GoalInfo] = Field(
        default_factory=list, description="Goals on the diagram"
    )
    balls: list[BallPosition] = Field(
        default_factory=list, description="Ball positions on the diagram"
    )
    zones: list[PitchZone] = Field(
        default_factory=list, description="Marked zones on the diagram"
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
