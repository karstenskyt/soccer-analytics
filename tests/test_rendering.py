"""Tests for pitch diagram rendering."""

from src.rendering.pitch import _color_for_role, render_drill_diagram
from src.schemas.session_plan import (
    DiagramInfo,
    DrillBlock,
    PlayerPosition,
)


def _make_drill(positions: list[PlayerPosition] | None = None) -> DrillBlock:
    """Create a DrillBlock with optional player positions."""
    diagram = DiagramInfo(player_positions=positions or [])
    return DrillBlock(name="Test Drill", diagram=diagram)


def _is_png(data: bytes) -> bool:
    """Check if bytes start with the PNG magic number."""
    return data[:8] == b"\x89PNG\r\n\x1a\n"


def _is_pdf(data: bytes) -> bool:
    """Check if bytes start with the PDF magic number."""
    return data[:5] == b"%PDF-"


def test_empty_drill_renders_valid_png():
    """An empty drill (no player positions) should render a clean pitch."""
    result = render_drill_diagram(_make_drill())
    assert isinstance(result, bytes)
    assert len(result) > 0
    assert _is_png(result)


def test_drill_with_positions_renders_png():
    """A drill with player positions should render a valid PNG."""
    positions = [
        PlayerPosition(label="GK", x=50.0, y=5.0, role="goalkeeper"),
        PlayerPosition(label="A1", x=30.0, y=60.0, role="attacker"),
        PlayerPosition(label="D1", x=70.0, y=40.0, role="defender"),
    ]
    result = render_drill_diagram(_make_drill(positions))
    assert _is_png(result)
    assert len(result) > 1000  # Should be a substantive image


def test_pdf_format_output():
    """Rendering with fmt='pdf' should produce valid PDF bytes."""
    result = render_drill_diagram(_make_drill(), fmt="pdf")
    assert isinstance(result, bytes)
    assert _is_pdf(result)


def test_role_color_mapping():
    """Role strings should map to expected colors."""
    assert _color_for_role("goalkeeper") == "#F9A825"
    assert _color_for_role("GK") == "#F9A825"
    assert _color_for_role("attacker") == "#1565C0"
    assert _color_for_role("defender") == "#C62828"
    assert _color_for_role("unknown_role") == "#1565C0"  # default
    assert _color_for_role(None) == "#1565C0"  # default


def test_role_colors_case_insensitive():
    """Role color lookup should be case-insensitive."""
    assert _color_for_role("Goalkeeper") == "#F9A825"
    assert _color_for_role("ATTACKER") == "#1565C0"
    assert _color_for_role("  Defender  ") == "#C62828"
