"""Pydantic models for tactical analysis (Peters/Schumacher 2v1 methodology)."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class SituationType(str, Enum):
    """Basic 2v1 situation types from Peters/Schumacher methodology."""

    FRONTAL = "Frontal"
    LATERAL = "Lateral"
    BEHIND = "Behind"
    BEFORE = "Before"


class LaneName(str, Enum):
    """Five vertical lanes of the pitch."""

    LEFT_WING = "left_wing"
    LEFT_HALF_SPACE = "left_half_space"
    CENTRAL_CORRIDOR = "central_corridor"
    RIGHT_HALF_SPACE = "right_half_space"
    RIGHT_WING = "right_wing"


class GameElement(str, Enum):
    """Nine game elements from Peters/Schumacher methodology."""

    COUNTER_ATTACK = "Counter Attack"
    FAST_BREAK = "Fast Break"
    POSITIONAL_ATTACK = "Positional Attack"
    PRESSING = "Pressing"
    COUNTER_PRESSING = "Counter Pressing"
    ORGANIZED_DEFENSE = "Organized Defense"
    BUILD_UP_PLAY = "Build-Up Play"
    TRANSITION_ATTACK = "Transition to Attack"
    TRANSITION_DEFENSE = "Transition to Defense"


class TacticalContext(BaseModel):
    """Tactical context linking a drill to methodology frameworks."""

    methodology: Optional[str] = Field(
        None, description="Methodology name (e.g., 'Peters/Schumacher 2v1')"
    )
    game_element: Optional[GameElement] = Field(
        None, description="Primary game element addressed"
    )
    lanes: list[LaneName] = Field(
        default_factory=list, description="Pitch lanes involved"
    )
    situation_type: Optional[SituationType] = Field(
        None, description="2v1 situation type"
    )
    phase_of_play: Optional[str] = Field(
        None,
        description="Phase of play (e.g., 'attacking', 'defending', 'transition')",
    )
    numerical_advantage: Optional[str] = Field(
        None, description="Numerical situation (e.g., '2v1', '3v2')"
    )
