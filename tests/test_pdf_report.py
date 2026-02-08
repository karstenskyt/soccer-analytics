"""Tests for PDF report generation."""

from unittest.mock import patch
from uuid import uuid4

import pytest

from src.rendering.pdf_report import generate_session_pdf
from src.schemas.session_plan import (
    DiagramInfo,
    DrillBlock,
    DrillSetup,
    PlayerPosition,
    SessionMetadata,
    SessionPlan,
    Source,
)
from src.schemas.tactical import (
    GameElement,
    LaneName,
    SituationType,
    TacticalContext,
)


def _make_plan(drills: list[DrillBlock] | None = None, **meta_kwargs) -> SessionPlan:
    """Create a SessionPlan with optional drills and metadata overrides."""
    defaults = {
        "title": "Test Session Plan",
        "category": "Goalkeeping: General",
        "difficulty": "Moderate",
        "author": "Test Coach",
    }
    defaults.update(meta_kwargs)
    return SessionPlan(
        metadata=SessionMetadata(**defaults),
        drills=drills or [],
        source=Source(filename="test.pdf", page_count=5),
    )


def _make_drill(name: str = "Test Drill", **kwargs) -> DrillBlock:
    """Create a DrillBlock with sensible defaults."""
    return DrillBlock(
        name=name,
        setup=kwargs.get("setup", DrillSetup(
            description="Set up cones in a grid",
            player_count="6 players",
            equipment=["cones", "balls"],
            area_dimensions="20x15 yards",
        )),
        diagram=kwargs.get("diagram", DiagramInfo()),
        sequence=kwargs.get("sequence", ["Pass to partner", "Receive and turn"]),
        coaching_points=kwargs.get("coaching_points", ["Keep head up", "First touch quality"]),
        rules=kwargs.get("rules", ["Two touches maximum"]),
        scoring=kwargs.get("scoring", []),
        progressions=kwargs.get("progressions", ["Add a defender"]),
        tactical_context=kwargs.get("tactical_context", None),
    )


def _is_pdf(data: bytes) -> bool:
    """Check if bytes start with the PDF magic number."""
    return data[:5] == b"%PDF-"


@patch("src.rendering.pdf_report._render_drill_diagram_png", return_value=None)
def test_generate_pdf_no_drills(mock_render):
    """PDF with 0 drills should produce cover + TOC only."""
    plan = _make_plan()
    result = generate_session_pdf(plan)
    assert isinstance(result, bytes)
    assert _is_pdf(result)
    assert len(result) > 100


@patch("src.rendering.pdf_report._render_drill_diagram_png", return_value=None)
def test_generate_pdf_single_drill(mock_render):
    """PDF with 1 drill should be valid."""
    plan = _make_plan(drills=[_make_drill()])
    result = generate_session_pdf(plan)
    assert _is_pdf(result)
    assert len(result) > 500


@patch("src.rendering.pdf_report._render_drill_diagram_png", return_value=None)
def test_generate_pdf_two_drills(mock_render):
    """PDF with 2 drills should be valid."""
    drills = [_make_drill("Drill A"), _make_drill("Drill B")]
    plan = _make_plan(drills=drills)
    result = generate_session_pdf(plan)
    assert _is_pdf(result)


@patch("src.rendering.pdf_report._render_drill_diagram_png", return_value=None)
def test_generate_pdf_many_drills(mock_render):
    """PDF with 10+ drills should be valid."""
    drills = [_make_drill(f"Drill {i}") for i in range(12)]
    plan = _make_plan(drills=drills)
    result = generate_session_pdf(plan)
    assert _is_pdf(result)
    # Should be larger than a single-drill PDF
    assert len(result) > 1000


@patch("src.rendering.pdf_report._render_drill_diagram_png", return_value=None)
def test_generate_pdf_with_tactical_context(mock_render):
    """PDF with tactical context should render the tactical box."""
    tc = TacticalContext(
        methodology="Peters/Schumacher 2v1",
        game_element=GameElement.COUNTER_ATTACK,
        lanes=[LaneName.CENTRAL_CORRIDOR, LaneName.LEFT_HALF_SPACE],
        situation_type=SituationType.FRONTAL,
        numerical_advantage="2v1",
    )
    drill = _make_drill(tactical_context=tc)
    plan = _make_plan(drills=[drill])
    result = generate_session_pdf(plan)
    assert _is_pdf(result)


@patch("src.rendering.pdf_report._render_drill_diagram_png", return_value=None)
def test_generate_pdf_without_tactical_context(mock_render):
    """PDF should work fine when drills have no tactical context."""
    drill = _make_drill(tactical_context=None)
    plan = _make_plan(drills=[drill])
    result = generate_session_pdf(plan)
    assert _is_pdf(result)


@patch("src.rendering.pdf_report._render_drill_diagram_png", return_value=None)
def test_generate_pdf_minimal_metadata(mock_render):
    """PDF should work with minimal metadata (only title required)."""
    plan = SessionPlan(
        metadata=SessionMetadata(title="Minimal Plan"),
        drills=[],
        source=Source(filename="min.pdf"),
    )
    result = generate_session_pdf(plan)
    assert _is_pdf(result)


@patch("src.rendering.pdf_report._render_drill_diagram_png", return_value=None)
def test_generate_pdf_drill_with_empty_lists(mock_render):
    """PDF should handle drills with empty sequences/coaching points."""
    drill = DrillBlock(
        name="Empty Drill",
        setup=DrillSetup(),
        diagram=DiagramInfo(),
        sequence=[],
        coaching_points=[],
        rules=[],
        scoring=[],
        progressions=[],
    )
    plan = _make_plan(drills=[drill])
    result = generate_session_pdf(plan)
    assert _is_pdf(result)


@patch("src.rendering.pdf_report._render_drill_diagram_png", return_value=None)
def test_generate_pdf_special_characters_in_title(mock_render):
    """PDF should handle special characters in titles."""
    plan = _make_plan(title="GK Training: Phase 1 & 2 (Advanced)")
    result = generate_session_pdf(plan)
    assert _is_pdf(result)
