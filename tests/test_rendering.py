"""Tests for pitch diagram rendering."""

from src.rendering.pitch import _color_for_role, _color_for_player, render_drill_diagram
from src.schemas.session_plan import (
    DiagramInfo,
    DrillBlock,
    PlayerPosition,
    MovementArrow,
    ArrowType,
    EquipmentObject,
    EquipmentType,
    GoalInfo,
    BallPosition,
    PitchZone,
    PitchView,
    PitchViewType,
)


def _make_drill(positions: list[PlayerPosition] | None = None) -> DrillBlock:
    """Create a DrillBlock with optional player positions."""
    diagram = DiagramInfo(player_positions=positions or [])
    return DrillBlock(name="Test Drill", diagram=diagram)


def _make_enriched_drill() -> DrillBlock:
    """Create a DrillBlock with full enriched diagram data."""
    diagram = DiagramInfo(
        vlm_description="2v1 frontal attack drill",
        player_positions=[
            PlayerPosition(label="A1", x=30, y=55, role="attacker"),
            PlayerPosition(label="A2", x=50, y=50, role="attacker"),
            PlayerPosition(label="D1", x=40, y=70, role="defender"),
            PlayerPosition(label="GK", x=50, y=95, role="goalkeeper"),
        ],
        pitch_view=PitchView(view_type=PitchViewType.HALF_PITCH),
        arrows=[
            MovementArrow(
                start_x=30, start_y=55, end_x=45, end_y=75,
                arrow_type=ArrowType.RUN, from_label="A1", sequence_number=1,
            ),
            MovementArrow(
                start_x=50, start_y=50, end_x=55, end_y=80,
                arrow_type=ArrowType.PASS, from_label="A2", to_label="A1",
                sequence_number=2,
            ),
        ],
        equipment=[
            EquipmentObject(equipment_type=EquipmentType.CONE, x=25, y=45),
            EquipmentObject(equipment_type=EquipmentType.CONE, x=55, y=45),
            EquipmentObject(
                equipment_type=EquipmentType.GATE,
                x=20, y=50, x2=20, y2=60, label="Gate 1",
            ),
        ],
        goals=[GoalInfo(x=50, y=100, goal_type="full_goal")],
        balls=[BallPosition(x=50, y=50)],
        zones=[
            PitchZone(
                zone_type="area", x1=20, y1=40, x2=80, y2=70,
                label="playing zone",
            ),
        ],
    )
    return DrillBlock(name="Enriched Drill", diagram=diagram)


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


# --- Player color tests ---


def test_color_for_player_prefers_explicit_color():
    """Explicit player color takes priority over role color."""
    pos = PlayerPosition(label="A1", x=30, y=55, role="attacker", color="red")
    assert _color_for_player(pos) == "#C62828"


def test_color_for_player_falls_back_to_role():
    """Without explicit color, falls back to role-based color."""
    pos = PlayerPosition(label="A1", x=30, y=55, role="attacker")
    assert _color_for_player(pos) == "#1565C0"


def test_color_for_player_unknown_color_falls_back():
    """Unknown explicit color falls back to role-based color."""
    pos = PlayerPosition(label="A1", x=30, y=55, role="attacker", color="magenta")
    assert _color_for_player(pos) == "#1565C0"


def test_color_for_player_no_role_no_color():
    """No role and no color returns default."""
    pos = PlayerPosition(label="X", x=50, y=50)
    assert _color_for_player(pos) == "#1565C0"


def test_drill_with_colored_players_renders():
    """Players with explicit colors should render valid PNG."""
    positions = [
        PlayerPosition(label="A1", x=30, y=60, role="attacker", color="red"),
        PlayerPosition(label="D1", x=70, y=40, role="defender", color="blue"),
        PlayerPosition(label="GK", x=50, y=5, role="goalkeeper", color="green"),
    ]
    result = render_drill_diagram(_make_drill(positions))
    assert _is_png(result)
    assert len(result) > 1000


# --- Enriched rendering tests ---


def test_enriched_drill_renders_valid_png():
    """A fully enriched drill should render without errors."""
    result = render_drill_diagram(_make_enriched_drill())
    assert _is_png(result)
    assert len(result) > 5000  # Should be larger due to extra elements


def test_enriched_drill_renders_pdf():
    """Enriched drill should also render to PDF."""
    result = render_drill_diagram(_make_enriched_drill(), fmt="pdf")
    assert _is_pdf(result)


def test_drill_with_only_arrows():
    """Arrows without other enriched elements should render fine."""
    diagram = DiagramInfo(
        arrows=[
            MovementArrow(
                start_x=20, start_y=30, end_x=60, end_y=70,
                arrow_type=ArrowType.SHOT,
            ),
        ],
    )
    drill = DrillBlock(name="Arrow Only", diagram=diagram)
    result = render_drill_diagram(drill)
    assert _is_png(result)


def test_drill_with_only_equipment():
    """Equipment without other enriched elements should render fine."""
    diagram = DiagramInfo(
        equipment=[
            EquipmentObject(equipment_type=EquipmentType.MANNEQUIN, x=50, y=50),
            EquipmentObject(equipment_type=EquipmentType.POLE, x=30, y=60),
        ],
    )
    drill = DrillBlock(name="Equipment Only", diagram=diagram)
    result = render_drill_diagram(drill)
    assert _is_png(result)


def test_drill_with_zones_and_balls():
    """Zones and balls should render without errors."""
    diagram = DiagramInfo(
        zones=[
            PitchZone(zone_type="box", x1=30, y1=60, x2=70, y2=90),
        ],
        balls=[
            BallPosition(x=50, y=50, label="B"),
        ],
    )
    drill = DrillBlock(name="Zones and Balls", diagram=diagram)
    result = render_drill_diagram(drill)
    assert _is_png(result)


# --- Gemini fixture rendering tests ---


from src.schemas.session_plan import SessionPlan
from tests.fixtures.gemini_extractions import (
    GEMINI_GKNEXUS,
    GEMINI_NIELSEN,
    GEMINI_ROBERTS,
    GEMINI_WHEDDON,
)


def test_gemini_gknexus_screen5_renders():
    """GkNexus Screen 5 (6-server bombardment) renders valid PNG."""
    plan = SessionPlan.model_validate(GEMINI_GKNEXUS)
    drill = plan.drills[1]  # Screen 5: 6-Server Bombardment
    result = render_drill_diagram(drill)
    assert _is_png(result)
    assert len(result) > 5000


def test_gemini_nielsen_setup3_renders():
    """Nielsen Setup 3 (4v4+3 with zones) renders valid PNG."""
    plan = SessionPlan.model_validate(GEMINI_NIELSEN)
    drill = plan.drills[1]  # Setup 3: 4v4+3 to Goals with Zones
    result = render_drill_diagram(drill)
    assert _is_png(result)
    assert len(result) > 5000


def test_gemini_roberts_cutback_renders():
    """Roberts cutback crossing drill renders valid PNG."""
    plan = SessionPlan.model_validate(GEMINI_ROBERTS)
    drill = plan.drills[0]
    result = render_drill_diagram(drill)
    assert _is_png(result)
    assert len(result) > 5000


def test_gemini_wheddon_handling_renders():
    """Wheddon angled shot-stopping drill renders valid PNG."""
    plan = SessionPlan.model_validate(GEMINI_WHEDDON)
    drill = plan.drills[0]
    result = render_drill_diagram(drill)
    assert _is_png(result)
    assert len(result) > 5000
