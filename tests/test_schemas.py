"""Tests for Pydantic schema models."""

from src.schemas.session_plan import (
    SessionPlan,
    SessionMetadata,
    DrillBlock,
    DrillSetup,
    DiagramInfo,
    PlayerPosition,
    PitchView,
    PitchViewType,
    MovementArrow,
    ArrowType,
    EquipmentObject,
    EquipmentType,
    GoalInfo,
    BallPosition,
    PitchZone,
    Source,
)
from src.schemas.tactical import (
    TacticalContext,
    SituationType,
    LaneName,
    GameElement,
)


def test_player_position_creation():
    pos = PlayerPosition(label="GK", x=50.0, y=5.0, role="goalkeeper")
    assert pos.label == "GK"
    assert pos.x == 50.0
    assert pos.y == 5.0
    assert pos.color is None


def test_player_position_with_color():
    pos = PlayerPosition(label="A1", x=30.0, y=60.0, role="attacker", color="red")
    assert pos.color == "red"


def test_drill_block_defaults():
    drill = DrillBlock(name="Test Drill")
    assert drill.name == "Test Drill"
    assert drill.sequence == []
    assert drill.coaching_points == []
    assert drill.tactical_context is None
    # New enriched fields default to empty
    assert drill.diagram.arrows == []
    assert drill.diagram.equipment == []
    assert drill.diagram.goals == []
    assert drill.diagram.balls == []
    assert drill.diagram.zones == []
    assert drill.diagram.pitch_view is None


def test_tactical_context_enums():
    tc = TacticalContext(
        methodology="Peters/Schumacher 2v1",
        game_element=GameElement.COUNTER_ATTACK,
        situation_type=SituationType.FRONTAL,
        lanes=[LaneName.CENTRAL_CORRIDOR],
        numerical_advantage="2v1",
    )
    assert tc.game_element == GameElement.COUNTER_ATTACK
    assert tc.situation_type.value == "Frontal"
    assert len(tc.lanes) == 1


def test_session_plan_full():
    plan = SessionPlan(
        metadata=SessionMetadata(title="Test Session"),
        drills=[DrillBlock(name="Drill 1")],
        source=Source(filename="test.pdf", page_count=2),
    )
    assert plan.metadata.title == "Test Session"
    assert len(plan.drills) == 1
    assert plan.source.filename == "test.pdf"


def test_session_plan_json_roundtrip():
    plan = SessionPlan(
        metadata=SessionMetadata(
            title="GK Session",
            category="Goalkeeping: General",
            difficulty="Moderate",
        ),
        drills=[
            DrillBlock(
                name="Coach-Goalkeeper(s)",
                setup=DrillSetup(
                    description="Setup description",
                    player_count="1 GK + Coach",
                    equipment=["balls", "cones"],
                ),
                coaching_points=["Stay on toes", "Quick hands"],
            )
        ],
        source=Source(filename="session.pdf", page_count=2),
    )
    json_data = plan.model_dump(mode="json")
    restored = SessionPlan.model_validate(json_data)
    assert restored.metadata.title == "GK Session"
    assert len(restored.drills) == 1
    assert restored.drills[0].coaching_points == [
        "Stay on toes",
        "Quick hands",
    ]


# --- Enriched schema model tests ---


def test_pitch_view_enum():
    pv = PitchView(view_type=PitchViewType.HALF_PITCH, orientation="vertical")
    assert pv.view_type == PitchViewType.HALF_PITCH
    assert pv.orientation == "vertical"
    assert pv.length_meters is None


def test_movement_arrow_creation():
    arrow = MovementArrow(
        start_x=30, start_y=55, end_x=45, end_y=75,
        arrow_type=ArrowType.RUN, from_label="A1", sequence_number=1,
    )
    assert arrow.arrow_type == ArrowType.RUN
    assert arrow.from_label == "A1"
    assert arrow.sequence_number == 1


def test_equipment_object_creation():
    eq = EquipmentObject(equipment_type=EquipmentType.CONE, x=25.0, y=45.0)
    assert eq.equipment_type == EquipmentType.CONE
    assert eq.x2 is None


def test_equipment_gate_with_endpoints():
    gate = EquipmentObject(
        equipment_type=EquipmentType.GATE,
        x=20.0, y=50.0, x2=20.0, y2=60.0,
    )
    assert gate.x2 == 20.0
    assert gate.y2 == 60.0


def test_goal_info():
    goal = GoalInfo(x=50.0, y=100.0, goal_type="full_goal", width_meters=7.32)
    assert goal.goal_type == "full_goal"
    assert goal.width_meters == 7.32


def test_ball_position():
    ball = BallPosition(x=50.0, y=50.0, label="B1")
    assert ball.label == "B1"


def test_pitch_zone():
    zone = PitchZone(
        zone_type="area", x1=20.0, y1=40.0, x2=80.0, y2=70.0,
        label="playing zone", color="#BBDEFB",
    )
    assert zone.label == "playing zone"


def test_diagram_info_enriched_roundtrip():
    """Test that enriched DiagramInfo survives JSON roundtrip."""
    diagram = DiagramInfo(
        description="2v1 frontal attack",
        player_positions=[
            PlayerPosition(label="A1", x=30, y=55, role="attacker"),
        ],
        pitch_view=PitchView(view_type=PitchViewType.HALF_PITCH),
        arrows=[
            MovementArrow(
                start_x=30, start_y=55, end_x=45, end_y=75,
                arrow_type=ArrowType.PASS, from_label="A1", to_label="A2",
            ),
        ],
        equipment=[
            EquipmentObject(equipment_type=EquipmentType.CONE, x=25, y=45),
        ],
        goals=[GoalInfo(x=50, y=100, goal_type="full_goal")],
        balls=[BallPosition(x=50, y=50)],
        zones=[
            PitchZone(zone_type="area", x1=20, y1=40, x2=80, y2=70),
        ],
    )
    json_data = diagram.model_dump(mode="json")
    restored = DiagramInfo.model_validate(json_data)
    assert len(restored.arrows) == 1
    assert restored.arrows[0].arrow_type == ArrowType.PASS
    assert len(restored.equipment) == 1
    assert restored.equipment[0].equipment_type == EquipmentType.CONE
    assert len(restored.goals) == 1
    assert len(restored.balls) == 1
    assert len(restored.zones) == 1
    assert restored.pitch_view.view_type == PitchViewType.HALF_PITCH


def test_arrow_type_enum_values():
    assert ArrowType.RUN.value == "run"
    assert ArrowType.PASS.value == "pass"
    assert ArrowType.SHOT.value == "shot"
    assert ArrowType.DRIBBLE.value == "dribble"


def test_equipment_type_enum_values():
    assert EquipmentType.CONE.value == "cone"
    assert EquipmentType.MANNEQUIN.value == "mannequin"
    assert EquipmentType.FULL_GOAL.value == "full_goal"


# --- New schema fields tests ---


def test_desired_outcome_on_metadata():
    meta = SessionMetadata(
        title="Test",
        desired_outcome="Improve positioning and balance",
    )
    assert meta.desired_outcome == "Improve positioning and balance"


def test_desired_outcome_default_none():
    meta = SessionMetadata(title="Test")
    assert meta.desired_outcome is None


def test_drill_type_and_directional():
    drill = DrillBlock(
        name="Test Drill",
        drill_type="Game-Related Practice",
        directional=True,
    )
    assert drill.drill_type == "Game-Related Practice"
    assert drill.directional is True


def test_drill_type_defaults_none():
    drill = DrillBlock(name="Test Drill")
    assert drill.drill_type is None
    assert drill.directional is None


# --- Gemini 5c fixture validation tests ---


from tests.fixtures.gemini_extractions import (
    GEMINI_NIELSEN,
    GEMINI_ROBERTS,
    GEMINI_WHEDDON,
    ALL_GEMINI_FIXTURES,
)


def test_gemini_nielsen_validates():
    """Karsten Nielsen session plan parses through model_validate cleanly."""
    plan = SessionPlan.model_validate(GEMINI_NIELSEN)
    assert plan.metadata.title == "Building Out From the Back — 4v4+3 Positional Play"
    assert len(plan.drills) == 2
    assert plan.metadata.desired_outcome is not None
    assert "positional rotations" in plan.metadata.desired_outcome


def test_gemini_roberts_validates():
    """Ashley Roberts session plan parses through model_validate cleanly."""
    plan = SessionPlan.model_validate(GEMINI_ROBERTS)
    assert plan.metadata.title == "Wide Play: Crossing & Cutback Finishing"
    assert len(plan.drills) == 1
    assert plan.drills[0].directional is True


def test_gemini_wheddon_validates():
    """Phil Wheddon session plan parses through model_validate cleanly."""
    plan = SessionPlan.model_validate(GEMINI_WHEDDON)
    assert plan.metadata.title == "Goalkeeper Handling & Shot-Stopping"
    assert plan.metadata.desired_outcome is not None
    assert "shots from angles" in plan.metadata.desired_outcome


def test_gemini_plans_have_enriched_diagrams():
    """All Gemini fixtures have non-empty enriched diagram data."""
    for fixture in ALL_GEMINI_FIXTURES:
        plan = SessionPlan.model_validate(fixture)
        for drill in plan.drills:
            assert len(drill.diagram.player_positions) > 0, (
                f"Drill '{drill.name}' has no player positions"
            )
            assert len(drill.diagram.arrows) > 0, (
                f"Drill '{drill.name}' has no arrows"
            )
            assert len(drill.diagram.equipment) > 0, (
                f"Drill '{drill.name}' has no equipment"
            )
