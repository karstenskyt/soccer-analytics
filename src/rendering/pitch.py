"""Render soccer pitch diagrams from DrillBlock data using mplsoccer."""

import io

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.patches as mpatches  # noqa: E402
from mplsoccer import Pitch  # noqa: E402

from src.schemas.session_plan import DrillBlock, ArrowType, EquipmentType  # noqa: E402

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


def _color_for_role(role: str | None) -> str:
    """Map a player role string to a hex color."""
    if role is None:
        return DEFAULT_COLOR
    key = role.strip().lower()
    return ROLE_COLORS.get(key, DEFAULT_COLOR)


def _render_zones(ax, drill: DrillBlock) -> None:
    """Layer 1: Render semi-transparent zone rectangles."""
    for zone in drill.diagram.zones:
        color = zone.color or ZONE_DEFAULT_COLOR
        x_min = min(zone.x1, zone.x2)
        y_min = min(zone.y1, zone.y2)
        width = abs(zone.x2 - zone.x1)
        height = abs(zone.y2 - zone.y1)
        rect = mpatches.FancyBboxPatch(
            (x_min, y_min), width, height,
            boxstyle="round,pad=0.5",
            facecolor=color, edgecolor=color,
            alpha=0.2, linewidth=1.0, zorder=1,
        )
        ax.add_patch(rect)
        if zone.label:
            ax.text(
                (zone.x1 + zone.x2) / 2, (zone.y1 + zone.y2) / 2,
                zone.label, fontsize=6, ha="center", va="center",
                color=color, alpha=0.6, zorder=1.5,
            )


def _render_equipment(ax, drill: DrillBlock) -> None:
    """Layer 2: Render equipment markers."""
    for eq in drill.diagram.equipment:
        style = EQUIPMENT_MARKERS.get(
            eq.equipment_type,
            {"marker": "o", "color": "#9E9E9E", "size": 80},
        )
        ax.scatter(
            eq.x, eq.y,
            s=style["size"], c=style["color"],
            marker=style["marker"],
            edgecolors="black", linewidths=0.5,
            zorder=2, alpha=0.9,
        )
        # For gates, draw a line between the two points
        if eq.x2 is not None and eq.y2 is not None:
            ax.plot(
                [eq.x, eq.x2], [eq.y, eq.y2],
                color=style["color"], linewidth=2.0,
                zorder=2, alpha=0.8,
            )
        if eq.label:
            ax.text(
                eq.x, eq.y - 3, eq.label,
                fontsize=5, ha="center", va="top",
                color="white", alpha=0.8, zorder=2.1,
            )


def _render_goals(ax, drill: DrillBlock) -> None:
    """Layer 2: Render goal markers at pitch edges."""
    for goal in drill.diagram.goals:
        width = goal.width_meters or 7.32  # standard goal width
        # Scale width to Opta coordinates (approximate: 7.32m ≈ 10 Opta units)
        half_w = (width / 7.32) * 5.0
        if goal.goal_type == "mini_goal":
            half_w = 2.5
        ax.plot(
            [goal.x - half_w, goal.x + half_w], [goal.y, goal.y],
            color="white", linewidth=3.0, solid_capstyle="round",
            zorder=2, alpha=0.9,
        )


def _render_arrows(ax, drill: DrillBlock) -> set[str]:
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

        dx = arrow.end_x - arrow.start_x
        dy = arrow.end_y - arrow.start_y

        ax.annotate(
            "",
            xy=(arrow.end_x, arrow.end_y),
            xytext=(arrow.start_x, arrow.start_y),
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
            mid_x = arrow.start_x + dx * 0.5
            mid_y = arrow.start_y + dy * 0.5
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
            mid_x = arrow.start_x + dx * 0.5
            mid_y = arrow.start_y + dy * 0.5
            ax.text(
                mid_x, mid_y + 2, arrow.label,
                fontsize=5, ha="center", va="bottom",
                color=style["color"], alpha=0.8,
                zorder=2.7,
            )

    return used_types


def _render_balls(ax, drill: DrillBlock) -> None:
    """Layer 3: Render ball positions as white circles."""
    for ball in drill.diagram.balls:
        ax.scatter(
            ball.x, ball.y,
            s=100, c="white", edgecolors="black",
            linewidths=1.5, zorder=3, marker="o",
        )
        if ball.label:
            ax.text(
                ball.x, ball.y - 3, ball.label,
                fontsize=5, ha="center", va="top",
                color="white", zorder=3.1,
            )


def _render_players(ax, drill: DrillBlock) -> None:
    """Layer 3-4: Render player positions with role-colored markers."""
    for pos in drill.diagram.player_positions:
        color = _color_for_role(pos.role)
        ax.scatter(
            pos.x, pos.y,
            s=MARKER_SIZE, c=color,
            edgecolors="white", linewidths=1.0,
            zorder=3,
        )
        ax.annotate(
            pos.label,
            (pos.x, pos.y),
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

    Renders all enriched elements in layers:
    1. Zones (zorder=1)
    2. Equipment (zorder=2)
    3. Goals (zorder=2)
    4. Arrows (zorder=2.5)
    5. Balls (zorder=3)
    6. Players (zorder=3-4)
    7. Legend

    Args:
        drill: DrillBlock containing diagram data.
        fmt: Output format ('png' or 'pdf').

    Returns:
        Image bytes in the requested format.
    """
    pitch = Pitch(pitch_type="opta", pitch_color="grass", line_color="white")
    fig, ax = pitch.draw(figsize=(10, 7))

    # Layer 1: Zones
    _render_zones(ax, drill)

    # Layer 2: Equipment
    _render_equipment(ax, drill)

    # Layer 2: Goals
    _render_goals(ax, drill)

    # Layer 2.5: Arrows
    used_arrow_types = _render_arrows(ax, drill)

    # Layer 3: Balls
    _render_balls(ax, drill)

    # Layer 3-4: Players
    _render_players(ax, drill)

    # Layer 5: Legend
    _render_legend(ax, used_arrow_types)

    ax.set_title(drill.name, fontsize=14, fontweight="bold", pad=10)

    buf = io.BytesIO()
    fig.savefig(buf, format=fmt, bbox_inches="tight", dpi=150)
    plt.close(fig)
    buf.seek(0)
    return buf.read()
