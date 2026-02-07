"""Tests for pipeline stages."""

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
