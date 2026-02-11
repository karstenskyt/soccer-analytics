"""Render soccer pitch diagrams from DrillBlock data using mplsoccer."""

import io
from typing import Callable

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.patches as mpatches  # noqa: E402
from mplsoccer import VerticalPitch  # noqa: E402

from src.schemas.session_plan import DrillBlock, ArrowType, EquipmentType, PlayerPosition  # noqa: E402

# Type alias for the coordinate transform callable.
CoordFn = Callable[[float, float], tuple[float, float]]

# Role-based marker colors (consistent with soccer-diagrams conventions)
ROLE_COLORS: dict[str, str] = {
    "goalkeeper": "#F9A825",
    "gk": "#F9A825",
    "attacker": "#1565C0",
    "attack": "#1565C0",
    "defender": "#C62828",
    "defense": "#C62828",
    "neutral": "#F9A825",
}

DEFAULT_COLOR = "#1565C0"
MARKER_SIZE = 200
FONT_SIZE = 8

# Arrow styling per type
ARROW_STYLES: dict[str, dict] = {
    ArrowType.RUN: {"color": "#1565C0", "linestyle": "-", "linewidth": 1.5},
    ArrowType.PASS: {"color": "#4CAF50", "linestyle": "--", "linewidth": 1.5},
    ArrowType.SHOT: {"color": "#FF5722", "linestyle": "-", "linewidth": 2.5},
    ArrowType.DRIBBLE: {"color": "#9C27B0", "linestyle": "-.", "linewidth": 1.5},
    ArrowType.CROSS: {"color": "#FF9800", "linestyle": "--", "linewidth": 1.5},
    ArrowType.THROUGH_BALL: {"color": "#00BCD4", "linestyle": ":", "linewidth": 1.8},
    ArrowType.MOVEMENT: {"color": "#607D8B", "linestyle": "-", "linewidth": 1.2},
}

# Equipment marker shapes and colors
EQUIPMENT_MARKERS: dict[str, dict] = {
    EquipmentType.CONE: {"marker": "^", "color": "#FF9800", "size": 80},
    EquipmentType.MANNEQUIN: {"marker": "s", "color": "#795548", "size": 100},
    EquipmentType.POLE: {"marker": "|", "color": "#9E9E9E", "size": 120},
    EquipmentType.GATE: {"marker": "d", "color": "#FFEB3B", "size": 90},
    EquipmentType.HURDLE: {"marker": "_", "color": "#607D8B", "size": 100},
    EquipmentType.MINI_GOAL: {"marker": "H", "color": "#E0E0E0", "size": 120},
    EquipmentType.FULL_GOAL: {"marker": "H", "color": "#FFFFFF", "size": 150},
    EquipmentType.FLAG: {"marker": "P", "color": "#F44336", "size": 80},
}

# Zone colors with alpha
ZONE_DEFAULT_COLOR = "#BBDEFB"

# ---------------------------------------------------------------------------
# Opta pitch geometry for mapping view-relative schema coords (0-100)
# into absolute Opta positions.  Opta: x = length 0-100, y = width 0-100.
# Penalty area ≈ x 83-100, y 21-79 in Opta.
# ---------------------------------------------------------------------------
_VIEW_BOUNDS: dict[str, dict[str, float]] = {
    "penalty_area": {"x_lo": 83.0, "x_hi": 100.0, "y_lo": 21.0, "y_hi": 79.0},
    "half_pitch":   {"x_lo": 50.0, "x_hi": 100.0, "y_lo":  0.0, "y_hi": 100.0},
    "third":        {"x_lo": 66.7, "x_hi": 100.0, "y_lo":  0.0, "y_hi": 100.0},
}


def _make_transform(view_type: str | None) -> CoordFn:
    """Build a coordinate transform for the given pitch view.

    Schema coordinates: x = width (0-100), y = length toward goal (0-100).
    These are *view-relative*: 0-100 spans the visible area, not the full pitch.

    Opta coordinates: x = pitch length (0-100), y = pitch width (0-100).

    VerticalPitch axes: ax_x = opta_y (width, horizontal),
                        ax_y = opta_x (length, vertical, goal at top).

    The returned function converts (schema_x, schema_y) → (ax_x, ax_y).
    """
    bounds = _VIEW_BOUNDS.get(view_type or "", {})
    x_lo = bounds.get("x_lo", 0.0)
    x_hi = bounds.get("x_hi", 100.0)
    y_lo = bounds.get("y_lo", 0.0)
    y_hi = bounds.get("y_hi", 100.0)

    def pc(sx: float, sy: float) -> tuple[float, float]:
        opta_x = x_lo + (sy / 100.0) * (x_hi - x_lo)   # length
        opta_y = y_lo + (sx / 100.0) * (y_hi - y_lo)    # width
        return opta_y, opta_x  # VerticalPitch: (ax_x=width, ax_y=length)

    return pc


def _color_for_role(role: str | None) -> str:
    """Map a player role string to a hex color."""
    if role is None:
        return DEFAULT_COLOR
    key = role.strip().lower()
    return ROLE_COLORS.get(key, DEFAULT_COLOR)


# Map diagram color names to hex colors for rendering
_DIAGRAM_COLORS: dict[str, str] = {
    "red": "#C62828",
    "green": "#2E7D32",
    "blue": "#1565C0",
    "yellow": "#F9A825",
    "white": "#FAFAFA",
    "black": "#212121",
    "orange": "#E65100",
    "grey": "#757575",
    "gray": "#757575",
}


def _color_for_player(pos: PlayerPosition) -> str:
    """Get render color for a player: prefer explicit color, fallback to role."""
    if pos.color:
        hex_color = _DIAGRAM_COLORS.get(pos.color.lower())
        if hex_color:
            return hex_color
    return _color_for_role(pos.role)


def _render_zones(ax, drill: DrillBlock, pc: CoordFn) -> None:
    """Layer 1: Render semi-transparent zone rectangles."""
    for zone in drill.diagram.zones:
        color = zone.color or ZONE_DEFAULT_COLOR
        c1x, c1y = pc(zone.x1, zone.y1)
        c2x, c2y = pc(zone.x2, zone.y2)
        x_min = min(c1x, c2x)
        y_min = min(c1y, c2y)
        width = abs(c2x - c1x)
        height = abs(c2y - c1y)
        rect = mpatches.FancyBboxPatch(
            (x_min, y_min), width, height,
            boxstyle="round,pad=0.5",
            facecolor=color, edgecolor=color,
            alpha=0.2, linewidth=1.0, zorder=1,
        )
        ax.add_patch(rect)
        if zone.label:
            cx, cy = pc(
                (zone.x1 + zone.x2) / 2,
                (zone.y1 + zone.y2) / 2,
            )
            ax.text(
                cx, cy, zone.label,
                fontsize=6, ha="center", va="center",
                color=color, alpha=0.6, zorder=1.5,
            )


def _render_equipment(ax, drill: DrillBlock, pc: CoordFn) -> None:
    """Layer 2: Render equipment markers."""
    for eq in drill.diagram.equipment:
        style = EQUIPMENT_MARKERS.get(
            eq.equipment_type,
            {"marker": "o", "color": "#9E9E9E", "size": 80},
        )
        ex, ey = pc(eq.x, eq.y)
        ax.scatter(
            ex, ey,
            s=style["size"], c=style["color"],
            marker=style["marker"],
            edgecolors="black", linewidths=0.5,
            zorder=2, alpha=0.9,
        )
        # For gates, draw a line between the two points
        if eq.x2 is not None and eq.y2 is not None:
            ex2, ey2 = pc(eq.x2, eq.y2)
            ax.plot(
                [ex, ex2], [ey, ey2],
                color=style["color"], linewidth=2.0,
                zorder=2, alpha=0.8,
            )
        if eq.label:
            ax.text(
                ex, ey - 2, eq.label,
                fontsize=5, ha="center", va="top",
                color="white", alpha=0.8, zorder=2.1,
            )


def _render_goals(ax, drill: DrillBlock, pc: CoordFn) -> None:
    """Layer 2: Render goal markers at pitch edges."""
    for goal in drill.diagram.goals:
        width = goal.width_meters or 7.32  # standard goal width
        # Scale width to Opta coordinates (7.32m on 68m wide pitch ≈ 10.8 units)
        half_w = (width / 7.32) * 5.4
        if goal.goal_type == "mini_goal":
            half_w = 2.5
        gx, gy = pc(goal.x, goal.y)
        # Goal line runs along the width axis (ax_x)
        ax.plot(
            [gx - half_w, gx + half_w], [gy, gy],
            color="white", linewidth=3.0, solid_capstyle="round",
            zorder=2, alpha=0.9,
        )


def _render_arrows(ax, drill: DrillBlock, pc: CoordFn) -> set[str]:
    """Layer 2.5: Render movement arrows with type-specific styles.

    Returns set of arrow type names used (for legend).
    """
    used_types: set[str] = set()
    for arrow in drill.diagram.arrows:
        style = ARROW_STYLES.get(
            arrow.arrow_type,
            {"color": "#607D8B", "linestyle": "-", "linewidth": 1.2},
        )
        used_types.add(arrow.arrow_type.value)

        sx, sy = pc(arrow.start_x, arrow.start_y)
        ex, ey = pc(arrow.end_x, arrow.end_y)

        ax.annotate(
            "",
            xy=(ex, ey),
            xytext=(sx, sy),
            arrowprops=dict(
                arrowstyle="->",
                color=style["color"],
                linestyle=style["linestyle"],
                linewidth=style["linewidth"],
                shrinkA=5, shrinkB=5,
            ),
            zorder=2.5,
        )

        # Sequence number badge
        if arrow.sequence_number is not None:
            mid_x = (sx + ex) / 2
            mid_y = (sy + ey) / 2
            ax.scatter(
                mid_x, mid_y, s=120, c="white",
                edgecolors=style["color"], linewidths=1.0,
                zorder=2.6,
            )
            ax.text(
                mid_x, mid_y, str(arrow.sequence_number),
                fontsize=6, ha="center", va="center",
                color=style["color"], fontweight="bold",
                zorder=2.7,
            )

        # Arrow label
        if arrow.label:
            mid_x = (sx + ex) / 2
            mid_y = (sy + ey) / 2
            ax.text(
                mid_x, mid_y + 1, arrow.label,
                fontsize=5, ha="center", va="bottom",
                color=style["color"], alpha=0.8,
                zorder=2.7,
            )

    return used_types


def _render_balls(ax, drill: DrillBlock, pc: CoordFn) -> None:
    """Layer 3: Render ball positions as white circles."""
    for ball in drill.diagram.balls:
        bx, by = pc(ball.x, ball.y)
        ax.scatter(
            bx, by,
            s=100, c="white", edgecolors="black",
            linewidths=1.5, zorder=3, marker="o",
        )
        if ball.label:
            ax.text(
                bx, by - 2, ball.label,
                fontsize=5, ha="center", va="top",
                color="white", zorder=3.1,
            )


def _render_players(ax, drill: DrillBlock, pc: CoordFn) -> None:
    """Layer 3-4: Render player positions with color-based markers."""
    for pos in drill.diagram.player_positions:
        color = _color_for_player(pos)
        px, py = pc(pos.x, pos.y)
        ax.scatter(
            px, py,
            s=MARKER_SIZE, c=color,
            edgecolors="white", linewidths=1.0,
            zorder=3,
        )
        ax.annotate(
            pos.label,
            (px, py),
            fontsize=FONT_SIZE,
            ha="center", va="center",
            color="white", fontweight="bold",
            zorder=4,
        )


def _render_legend(ax, used_arrow_types: set[str]) -> None:
    """Layer 5: Auto-generated legend from arrow types present."""
    if not used_arrow_types:
        return

    legend_handles = []
    for arrow_type_str in sorted(used_arrow_types):
        try:
            arrow_type = ArrowType(arrow_type_str)
        except ValueError:
            continue
        style = ARROW_STYLES.get(arrow_type, {})
        if not style:
            continue
        handle = mpatches.Patch(
            color=style["color"],
            label=arrow_type_str.replace("_", " ").title(),
        )
        legend_handles.append(handle)

    if legend_handles:
        ax.legend(
            handles=legend_handles,
            loc="upper right",
            fontsize=6,
            framealpha=0.7,
            fancybox=True,
        )


def render_drill_diagram(drill: DrillBlock, fmt: str = "png") -> bytes:
    """Render a pitch diagram for a drill block.

    Uses VerticalPitch with the correct view (full, half, penalty area)
    based on ``drill.diagram.pitch_view``.  Schema coordinates (x=width,
    y=length-toward-goal, both 0-100 within the view area) are rescaled
    to absolute Opta positions so pitch markings align with drill elements.

    Layers:
        1. Zones  (zorder 1)
        2. Equipment + Goals  (zorder 2)
        3. Arrows  (zorder 2.5)
        4. Balls  (zorder 3)
        5. Players  (zorder 3-4)
        6. Legend

    Args:
        drill: DrillBlock containing diagram data.
        fmt: Output format ('png' or 'pdf').

    Returns:
        Image bytes in the requested format.
    """
    view_type = None
    if drill.diagram.pitch_view:
        view_type = drill.diagram.pitch_view.view_type

    use_half = view_type in ("half_pitch", "penalty_area", "third")

    pitch = VerticalPitch(
        pitch_type="opta",
        pitch_color="grass",
        line_color="white",
        half=use_half,
    )

    # Figsize tuned per view: penalty area is wide, full pitch is tall.
    if view_type == "penalty_area":
        figsize = (10, 7)
    elif use_half:
        figsize = (10, 10)
    else:
        figsize = (10, 14)

    fig, ax = pitch.draw(figsize=figsize)

    pc = _make_transform(view_type)

    # Extra zoom for penalty-area view (half pitch shows opta_x 50-100;
    # penalty area is opta_x ~83-100).  ax y-axis = opta_x on VerticalPitch.
    if view_type == "penalty_area":
        ax.set_ylim(78, 102)
        ax.set_xlim(15, 85)

    # Layer 1: Zones
    _render_zones(ax, drill, pc)

    # Layer 2: Equipment
    _render_equipment(ax, drill, pc)

    # Layer 2: Goals
    _render_goals(ax, drill, pc)

    # Layer 2.5: Arrows
    used_arrow_types = _render_arrows(ax, drill, pc)

    # Layer 3: Balls
    _render_balls(ax, drill, pc)

    # Layer 3-4: Players
    _render_players(ax, drill, pc)

    # Layer 5: Legend
    _render_legend(ax, used_arrow_types)

    ax.set_title(drill.name, fontsize=14, fontweight="bold", pad=10)

    buf = io.BytesIO()
    fig.savefig(buf, format=fmt, bbox_inches="tight", dpi=150)
    plt.close(fig)
    buf.seek(0)
    return buf.read()
