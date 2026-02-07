"""Stage 4: Validation and enrichment of extracted session plans."""

import logging
import re

from src.schemas.session_plan import SessionPlan, DrillBlock
from src.schemas.tactical import (
    TacticalContext,
    SituationType,
    LaneName,
    GameElement,
)

logger = logging.getLogger(__name__)

# Keywords that suggest specific game elements
GAME_ELEMENT_KEYWORDS: dict[str, GameElement] = {
    "counter attack": GameElement.COUNTER_ATTACK,
    "counter-attack": GameElement.COUNTER_ATTACK,
    "fast break": GameElement.FAST_BREAK,
    "positional": GameElement.POSITIONAL_ATTACK,
    "pressing": GameElement.PRESSING,
    "counter press": GameElement.COUNTER_PRESSING,
    "gegenpressing": GameElement.COUNTER_PRESSING,
    "organized defense": GameElement.ORGANIZED_DEFENSE,
    "defensive organization": GameElement.ORGANIZED_DEFENSE,
    "build up": GameElement.BUILD_UP_PLAY,
    "build-up": GameElement.BUILD_UP_PLAY,
    "transition to attack": GameElement.TRANSITION_ATTACK,
    "transition to defense": GameElement.TRANSITION_DEFENSE,
}

SITUATION_KEYWORDS: dict[str, SituationType] = {
    "frontal": SituationType.FRONTAL,
    "face to face": SituationType.FRONTAL,
    "lateral": SituationType.LATERAL,
    "side": SituationType.LATERAL,
    "behind": SituationType.BEHIND,
    "from behind": SituationType.BEHIND,
    "before": SituationType.BEFORE,
    "in front": SituationType.BEFORE,
}

LANE_KEYWORDS: dict[str, LaneName] = {
    "left wing": LaneName.LEFT_WING,
    "left flank": LaneName.LEFT_WING,
    "left half": LaneName.LEFT_HALF_SPACE,
    "left half-space": LaneName.LEFT_HALF_SPACE,
    "central": LaneName.CENTRAL_CORRIDOR,
    "center": LaneName.CENTRAL_CORRIDOR,
    "middle": LaneName.CENTRAL_CORRIDOR,
    "right half": LaneName.RIGHT_HALF_SPACE,
    "right half-space": LaneName.RIGHT_HALF_SPACE,
    "right wing": LaneName.RIGHT_WING,
    "right flank": LaneName.RIGHT_WING,
}


def _detect_game_element(text: str) -> GameElement | None:
    """Detect game element from text content."""
    text_lower = text.lower()
    for keyword, element in GAME_ELEMENT_KEYWORDS.items():
        if keyword in text_lower:
            return element
    return None


def _detect_situation_type(text: str) -> SituationType | None:
    """Detect 2v1 situation type from text content."""
    text_lower = text.lower()
    for keyword, situation in SITUATION_KEYWORDS.items():
        if keyword in text_lower:
            return situation
    return None


def _detect_lanes(text: str) -> list[LaneName]:
    """Detect pitch lanes mentioned in text."""
    text_lower = text.lower()
    lanes: list[LaneName] = []
    for keyword, lane in LANE_KEYWORDS.items():
        if keyword in text_lower and lane not in lanes:
            lanes.append(lane)
    return lanes


def _detect_methodology(text: str) -> str | None:
    """Detect if Peters/Schumacher or other methodology is referenced."""
    text_lower = text.lower()
    if any(
        kw in text_lower
        for kw in ("peters", "schumacher", "2v1", "2 v 1")
    ):
        return "Peters/Schumacher 2v1"
    if "rondo" in text_lower:
        return "Rondo"
    if "positional play" in text_lower:
        return "Positional Play"
    return None


def _enrich_drill_tactical_context(drill: DrillBlock) -> DrillBlock:
    """Enrich a drill with tactical context based on text analysis."""
    all_text = " ".join(
        [
            drill.name,
            drill.setup.description,
            drill.diagram.vlm_description,
            " ".join(drill.sequence),
            " ".join(drill.coaching_points),
            " ".join(drill.rules),
            " ".join(drill.progressions),
        ]
    )

    methodology = _detect_methodology(all_text)
    game_element = _detect_game_element(all_text)
    situation_type = _detect_situation_type(all_text)
    lanes = _detect_lanes(all_text)

    # Detect numerical advantage
    numerical = None
    num_match = re.search(
        r"(\d+)\s*(?:v|vs|versus)\s*(\d+)", all_text, re.IGNORECASE
    )
    if num_match:
        numerical = f"{num_match.group(1)}v{num_match.group(2)}"

    if any([methodology, game_element, situation_type, lanes, numerical]):
        drill.tactical_context = TacticalContext(
            methodology=methodology,
            game_element=game_element,
            situation_type=situation_type,
            lanes=lanes,
            numerical_advantage=numerical,
        )

    return drill


async def validate_and_enrich(session_plan: SessionPlan) -> SessionPlan:
    """Validate and enrich a session plan with tactical context.

    Args:
        session_plan: Raw extracted session plan.

    Returns:
        Enriched session plan with tactical context and validation.
    """
    logger.info(f"Validating and enriching: {session_plan.metadata.title}")

    enriched_drills = []
    for drill in session_plan.drills:
        enriched = _enrich_drill_tactical_context(drill)
        enriched_drills.append(enriched)

    session_plan.drills = enriched_drills

    # Log quality warnings
    if not session_plan.metadata.title:
        logger.warning("Session plan has no title")

    if not session_plan.drills:
        logger.warning("Session plan has no drill blocks extracted")

    for drill in session_plan.drills:
        if not drill.coaching_points:
            logger.warning(f"Drill '{drill.name}' has no coaching points")
        if not drill.sequence:
            logger.warning(f"Drill '{drill.name}' has no sequence steps")

    logger.info(
        f"Enrichment complete: {len(enriched_drills)} drills processed"
    )
    return session_plan
