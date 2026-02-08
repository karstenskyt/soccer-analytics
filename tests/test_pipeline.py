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
    "sqlalchemy",
    "sqlalchemy.ext",
    "sqlalchemy.ext.asyncio",
]
for mod in _DOCKER_ONLY_MODULES:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

from src.pipeline.describe import _extract_json_from_text, _validate_positions
from src.pipeline.extract import _parse_player_positions
from src.pipeline.validate import (
    _detect_game_element,
    _detect_situation_type,
    _detect_lanes,
    _detect_methodology,
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
