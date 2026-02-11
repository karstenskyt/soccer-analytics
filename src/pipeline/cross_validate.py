"""Cross-validate CV preprocessing results against VLM extraction output."""

import logging

logger = logging.getLogger(__name__)


def cross_validate(diagram_data: dict) -> dict:
    """Cross-validate and merge CV + VLM results for a single diagram.

    Applies conflict resolution rules:
    1. Player count: if CV and VLM differ by >2, warn (CV is likely more accurate for count)
    2. Player colors: if VLM players missing color, try to fill from CV circle data
    3. Pitch view: if VLM = null, use CV estimate
    4. Goals in equipment: move any equipment_type=="full_goal" to goals array
    5. Degenerate arrows: remove arrows where start == end

    Args:
        diagram_data: merged dict from multi-pass extraction (includes _cv_analysis)

    Returns:
        Cleaned and cross-validated diagram data dict.
    """
    cv = diagram_data.pop("_cv_analysis", None)
    if cv is None:
        return diagram_data

    players = diagram_data.get("player_positions", [])
    cv_total = cv.get("total_circles", 0)
    vlm_total = len(players)

    # Rule 1: Player count cross-check
    if abs(cv_total - vlm_total) > 2:
        logger.warning(
            f"Player count mismatch: CV={cv_total}, VLM={vlm_total}. "
            f"CV circle breakdown: {cv.get('circles_by_color', {})}"
        )

    # Rule 2: Fill missing player colors from CV circles
    cv_circles = cv.get("circles", [])
    for player in players:
        if not player.get("color") and cv_circles:
            # Find nearest CV circle
            px, py = player.get("x", 50), player.get("y", 50)
            nearest = min(
                cv_circles,
                key=lambda c: (c["x"] - px) ** 2 + (c["y"] - py) ** 2,
            )
            dist = ((nearest["x"] - px) ** 2 + (nearest["y"] - py) ** 2) ** 0.5
            if dist < 15:  # Within 15% distance
                player["color"] = nearest["color"]

    # Rule 3: Pitch view fallback
    pitch_view = diagram_data.get("pitch_view")
    if pitch_view is None and cv.get("estimated_pitch_view"):
        diagram_data["pitch_view"] = {"view_type": cv["estimated_pitch_view"]}

    # Rule 4: Move full_goal from equipment to goals
    equipment = diagram_data.get("equipment", [])
    goals = diagram_data.get("goals", [])
    remaining_equipment = []
    for eq in equipment:
        if eq.get("equipment_type") == "full_goal":
            goals.append(
                {
                    "x": eq.get("x", 50),
                    "y": eq.get("y", 100),
                    "goal_type": "full_goal",
                }
            )
        else:
            remaining_equipment.append(eq)
    diagram_data["equipment"] = remaining_equipment
    diagram_data["goals"] = goals

    # Rule 5: Remove degenerate arrows (start == end)
    arrows = diagram_data.get("arrows", [])
    valid_arrows = []
    for arrow in arrows:
        dx = abs(arrow.get("start_x", 0) - arrow.get("end_x", 0))
        dy = abs(arrow.get("start_y", 0) - arrow.get("end_y", 0))
        if dx + dy > 2:  # At least 2 units of movement
            valid_arrows.append(arrow)
    diagram_data["arrows"] = valid_arrows

    return diagram_data
