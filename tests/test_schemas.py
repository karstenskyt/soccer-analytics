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
        vlm_description="2v1 frontal attack",
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
