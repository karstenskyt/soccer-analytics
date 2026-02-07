"""Render soccer pitch diagrams from DrillBlock data using mplsoccer."""

import io

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from mplsoccer import Pitch  # noqa: E402

from src.schemas.session_plan import DrillBlock  # noqa: E402

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


def _color_for_role(role: str | None) -> str:
    """Map a player role string to a hex color."""
    if role is None:
        return DEFAULT_COLOR
    key = role.strip().lower()
    return ROLE_COLORS.get(key, DEFAULT_COLOR)


def render_drill_diagram(drill: DrillBlock, fmt: str = "png") -> bytes:
    """Render a pitch diagram for a drill block.

    Args:
        drill: DrillBlock containing player_positions in its diagram.
        fmt: Output format ('png' or 'pdf').

    Returns:
        Image bytes in the requested format.
    """
    pitch = Pitch(pitch_type="opta", pitch_color="grass", line_color="white")
    fig, ax = pitch.draw(figsize=(10, 7))

    positions = drill.diagram.player_positions
    if positions:
        for pos in positions:
            color = _color_for_role(pos.role)
            ax.scatter(
                pos.x,
                pos.y,
                s=MARKER_SIZE,
                c=color,
                edgecolors="white",
                linewidths=1.0,
                zorder=3,
            )
            ax.annotate(
                pos.label,
                (pos.x, pos.y),
                fontsize=FONT_SIZE,
                ha="center",
                va="center",
                color="white",
                fontweight="bold",
                zorder=4,
            )

    ax.set_title(drill.name, fontsize=14, fontweight="bold", pad=10)

    buf = io.BytesIO()
    fig.savefig(buf, format=fmt, bbox_inches="tight", dpi=150)
    plt.close(fig)
    buf.seek(0)
    return buf.read()
