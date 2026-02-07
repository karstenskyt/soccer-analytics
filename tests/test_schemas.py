"""Tests for Pydantic schema models."""

from src.schemas.session_plan import (
    SessionPlan,
    SessionMetadata,
    DrillBlock,
    DrillSetup,
    DiagramInfo,
    PlayerPosition,
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
