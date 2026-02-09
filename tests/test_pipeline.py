"""Tests for pipeline stages."""

import sys
from unittest.mock import MagicMock

# Mock heavy dependencies that aren't installed locally (Docker-only)
_DOCKER_ONLY_MODULES = [
    "docling",
    "docling.document_converter",
    "docling.datamodel",
    "docling.datamodel.base_models",
    "docling.datamodel.pipeline_options",
    "docling_core",
    "docling_core.types",
    "docling_core.types.doc",
    "sqlalchemy",
    "sqlalchemy.ext",
    "sqlalchemy.ext.asyncio",
]
for mod in _DOCKER_ONLY_MODULES:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

from src.pipeline.describe import _extract_json_from_text, _validate_positions
from src.pipeline.extract import (
    _parse_player_positions,
    _parse_pitch_view,
    _parse_movement_arrows,
    _parse_equipment,
    _parse_goals,
    _parse_balls,
    _parse_zones,
)
from src.pipeline.validate import (
    _detect_game_element,
    _detect_situation_type,
    _detect_lanes,
    _detect_methodology,
)
from src.schemas.session_plan import (
    PitchViewType,
    ArrowType,
    EquipmentType,
)
from src.schemas.tactical import GameElement, SituationType, LaneName


def test_detect_game_element():
    assert _detect_game_element("counter attack drill") == GameElement.COUNTER_ATTACK
    assert _detect_game_element("pressing exercise") == GameElement.PRESSING
    assert _detect_game_element("build-up play") == GameElement.BUILD_UP_PLAY
    assert _detect_game_element("basic warm up") is None


def test_detect_situation_type():
    assert _detect_situation_type("frontal 2v1") == SituationType.FRONTAL
    assert _detect_situation_type("lateral movement") == SituationType.LATERAL
    assert _detect_situation_type("attack from behind") == SituationType.BEHIND
    assert _detect_situation_type("simple pass") is None


def test_detect_lanes():
    lanes = _detect_lanes("play through the central corridor")
    assert LaneName.CENTRAL_CORRIDOR in lanes

    lanes = _detect_lanes("left wing and right wing overlap")
    assert LaneName.LEFT_WING in lanes
    assert LaneName.RIGHT_WING in lanes


def test_detect_methodology():
    assert _detect_methodology("Peters 2v1 concept") == "Peters/Schumacher 2v1"
    assert _detect_methodology("Schumacher method") == "Peters/Schumacher 2v1"
    assert _detect_methodology("rondo exercise") == "Rondo"
    assert _detect_methodology("simple drill") is None


# --- Position extraction tests (Pass 2) ---


def test_validate_positions_clamps_coordinates():
    raw = [
        {"label": "A1", "x": 150, "y": 50, "role": "attacker"},
        {"label": "D1", "x": 30, "y": -10, "role": "defender"},
    ]
    result = _validate_positions(raw)
    assert len(result) == 2
    assert result[0]["x"] == 100.0
    assert result[0]["y"] == 50.0
    assert result[1]["x"] == 30.0
    assert result[1]["y"] == 0.0


def test_validate_positions_rejects_empty_labels():
    raw = [
        {"label": "", "x": 50, "y": 50, "role": "attacker"},
        {"label": "   ", "x": 50, "y": 50, "role": "defender"},
        {"label": "A1", "x": 50, "y": 50, "role": "attacker"},
    ]
    result = _validate_positions(raw)
    assert len(result) == 1
    assert result[0]["label"] == "A1"


def test_validate_positions_standardizes_roles():
    raw = [
        {"label": "GK", "x": 50, "y": 5, "role": "gk"},
        {"label": "A1", "x": 30, "y": 60, "role": "forward"},
        {"label": "D1", "x": 40, "y": 70, "role": "back"},
        {"label": "N1", "x": 50, "y": 50, "role": "banana"},
    ]
    result = _validate_positions(raw)
    assert result[0]["role"] == "goalkeeper"
    assert result[1]["role"] == "attacker"
    assert result[2]["role"] == "defender"
    assert result[3]["role"] is None  # unknown role → None


def test_validate_positions_deduplicates():
    raw = [
        {"label": "A1", "x": 30, "y": 60, "role": "attacker"},
        {"label": "A1", "x": 70, "y": 80, "role": "attacker"},
        {"label": "D1", "x": 50, "y": 50, "role": "defender"},
    ]
    result = _validate_positions(raw)
    assert len(result) == 2
    # First occurrence wins
    assert result[0]["x"] == 30.0
    assert result[0]["y"] == 60.0


def test_extract_json_position_payload():
    text = '{"player_positions": [{"label": "A1", "x": 30, "y": 60, "role": "attacker"}]}'
    parsed = _extract_json_from_text(text)
    assert parsed is not None
    assert len(parsed["player_positions"]) == 1
    assert parsed["player_positions"][0]["label"] == "A1"


def test_extract_json_position_with_markdown_fences():
    text = '```json\n{"player_positions": [{"label": "GK", "x": 50, "y": 5, "role": "goalkeeper"}]}\n```'
    parsed = _extract_json_from_text(text)
    assert parsed is not None
    assert parsed["player_positions"][0]["role"] == "goalkeeper"


def test_parse_player_positions_clamped():
    """Verify _parse_player_positions in extract.py clamps coordinates."""
    positions_data = [
        {"label": "A1", "x": 200, "y": -50, "role": "attacker"},
        {"label": "", "x": 50, "y": 50, "role": "attacker"},
        {"label": "D1", "x": 40, "y": 70, "role": "defender"},
    ]
    result = _parse_player_positions(positions_data)
    assert len(result) == 2  # empty label skipped
    assert result[0].x == 100.0
    assert result[0].y == 0.0
    assert result[1].x == 40.0
    assert result[1].y == 70.0


# --- Think-tag stripping tests ---


def test_extract_json_strips_think_tags():
    """Qwen3-VL <think> blocks should be stripped before JSON parsing."""
    text = '<think>Let me analyze this image...\nI see players and arrows.</think>{"is_diagram": true, "description": "2v1 drill"}'
    parsed = _extract_json_from_text(text)
    assert parsed is not None
    assert parsed["is_diagram"] is True
    assert parsed["description"] == "2v1 drill"


def test_extract_json_strips_multiline_think_tags():
    """Multi-line think blocks should also be stripped."""
    text = """<think>
This appears to be a soccer coaching diagram.
I can see player markers labeled A1, A2, D1.
There are arrows indicating movement.
</think>
{"is_diagram": true, "description": "2v1 attack drill", "player_positions": []}"""
    parsed = _extract_json_from_text(text)
    assert parsed is not None
    assert parsed["is_diagram"] is True


def test_extract_json_only_think_tags_returns_none():
    """If VLM only outputs think tags and no JSON, return None."""
    text = '<think>I cannot determine what this image shows.</think>'
    parsed = _extract_json_from_text(text)
    assert parsed is None


def test_extract_json_strips_unclosed_think_tags():
    """Unclosed <think> blocks (token limit hit) should still allow JSON extraction."""
    text = '<think>This is a long reasoning block that got truncated because the token limit was reached before the closing tag...{"is_diagram": true, "description": "2v1 drill"}'
    parsed = _extract_json_from_text(text)
    assert parsed is not None
    assert parsed["is_diagram"] is True


def test_extract_json_unclosed_think_no_json_returns_none():
    """Unclosed <think> with no JSON at all returns None."""
    text = '<think>Reasoning that consumed all tokens with no JSON output at all'
    parsed = _extract_json_from_text(text)
    assert parsed is None


# --- Enriched parsing helper tests ---


def test_parse_pitch_view():
    data = {"view_type": "half_pitch", "orientation": "vertical"}
    pv = _parse_pitch_view(data)
    assert pv is not None
    assert pv.view_type == PitchViewType.HALF_PITCH
    assert pv.orientation == "vertical"


def test_parse_pitch_view_unknown_type():
    data = {"view_type": "unknown_type"}
    pv = _parse_pitch_view(data)
    assert pv is not None
    assert pv.view_type == PitchViewType.HALF_PITCH  # fallback


def test_parse_pitch_view_none():
    assert _parse_pitch_view(None) is None
    assert _parse_pitch_view({}) is None


def test_parse_movement_arrows():
    data = [
        {
            "start_x": 30, "start_y": 55, "end_x": 45, "end_y": 75,
            "arrow_type": "run", "from_label": "A1", "sequence_number": 1,
        },
        {
            "start_x": 50, "start_y": 50, "end_x": 55, "end_y": 80,
            "arrow_type": "pass", "from_label": "A2", "to_label": "A1",
        },
    ]
    arrows = _parse_movement_arrows(data)
    assert len(arrows) == 2
    assert arrows[0].arrow_type == ArrowType.RUN
    assert arrows[0].from_label == "A1"
    assert arrows[1].arrow_type == ArrowType.PASS


def test_parse_movement_arrows_clamps_coords():
    data = [{"start_x": -10, "start_y": 150, "end_x": 200, "end_y": -5}]
    arrows = _parse_movement_arrows(data)
    assert len(arrows) == 1
    assert arrows[0].start_x == 0.0
    assert arrows[0].start_y == 100.0
    assert arrows[0].end_x == 100.0
    assert arrows[0].end_y == 0.0


def test_parse_movement_arrows_unknown_type():
    data = [{"start_x": 30, "start_y": 55, "end_x": 45, "end_y": 75, "arrow_type": "banana"}]
    arrows = _parse_movement_arrows(data)
    assert len(arrows) == 1
    assert arrows[0].arrow_type == ArrowType.MOVEMENT  # fallback


def test_parse_equipment():
    data = [
        {"equipment_type": "cone", "x": 25, "y": 45},
        {"equipment_type": "mannequin", "x": 50, "y": 60, "label": "M1"},
    ]
    equipment = _parse_equipment(data)
    assert len(equipment) == 2
    assert equipment[0].equipment_type == EquipmentType.CONE
    assert equipment[1].label == "M1"


def test_parse_equipment_with_gate():
    data = [{"equipment_type": "gate", "x": 20, "y": 50, "x2": 20, "y2": 60}]
    equipment = _parse_equipment(data)
    assert len(equipment) == 1
    assert equipment[0].x2 == 20.0
    assert equipment[0].y2 == 60.0


def test_parse_goals():
    data = [
        {"x": 50, "y": 100, "goal_type": "full_goal"},
        {"x": 50, "y": 0, "goal_type": "mini_goal", "width_meters": 3.0},
    ]
    goals = _parse_goals(data)
    assert len(goals) == 2
    assert goals[0].goal_type == "full_goal"
    assert goals[1].width_meters == 3.0


def test_parse_balls():
    data = [
        {"x": 50, "y": 50},
        {"x": 30, "y": 60, "label": "B1"},
    ]
    balls = _parse_balls(data)
    assert len(balls) == 2
    assert balls[1].label == "B1"


def test_parse_zones():
    data = [
        {"zone_type": "area", "x1": 20, "y1": 40, "x2": 80, "y2": 70, "label": "zone1"},
    ]
    zones = _parse_zones(data)
    assert len(zones) == 1
    assert zones[0].label == "zone1"
    assert zones[0].x1 == 20.0


def test_parse_zones_clamps_coords():
    data = [{"x1": -10, "y1": -20, "x2": 150, "y2": 200}]
    zones = _parse_zones(data)
    assert len(zones) == 1
    assert zones[0].x1 == 0.0
    assert zones[0].y1 == 0.0
    assert zones[0].x2 == 100.0
    assert zones[0].y2 == 100.0
