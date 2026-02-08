"""Tests for MCP server tool logic with mocked httpx."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.mcp.server import (
    analyze_tactical_drill,
    export_session_pdf,
    parse_session_plan,
    render_drill_diagram,
    search_drills,
)


def _mock_response(status_code: int = 200, json_data: dict | None = None, content: bytes = b""):
    """Create a mock httpx.Response (sync methods, matching real httpx)."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data or {}
    mock.content = content
    if status_code >= 400:
        mock.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return mock


@pytest.mark.asyncio
async def test_parse_session_plan_list():
    """parse_session_plan with no plan_id should list sessions."""
    api_data = {"sessions": [{"id": "abc-123", "title": "GK Session"}], "count": 1}

    with patch("src.mcp.server._api_get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _mock_response(json_data=api_data)
        result = await parse_session_plan()

    parsed = json.loads(result)
    assert "sessions" in parsed
    assert len(parsed["sessions"]) == 1
    mock_get.assert_called_once_with("/api/sessions")


@pytest.mark.asyncio
async def test_parse_session_plan_by_id():
    """parse_session_plan with a plan_id should return the full plan."""
    plan_data = {"id": "abc-123", "metadata": {"title": "GK Session"}, "drills": []}

    with patch("src.mcp.server._api_get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _mock_response(json_data=plan_data)
        result = await parse_session_plan(plan_id="abc-123")

    parsed = json.loads(result)
    assert parsed["id"] == "abc-123"
    mock_get.assert_called_once_with("/api/sessions/abc-123")


@pytest.mark.asyncio
async def test_parse_session_plan_not_found():
    """parse_session_plan with unknown ID should return error."""
    with patch("src.mcp.server._api_get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _mock_response(status_code=404)
        result = await parse_session_plan(plan_id="nonexistent")

    parsed = json.loads(result)
    assert "error" in parsed


@pytest.mark.asyncio
async def test_analyze_tactical_drill_returns_drill():
    """analyze_tactical_drill should return drill JSON."""
    drill_data = {
        "name": "2v1 Frontal",
        "tactical_context": {"game_element": "Counter Attack"},
    }

    with patch("src.mcp.server._api_get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _mock_response(json_data=drill_data)
        result = await analyze_tactical_drill(plan_id="abc-123", drill_index=0)

    parsed = json.loads(result)
    assert parsed["name"] == "2v1 Frontal"
    assert "diagram_url" not in parsed


@pytest.mark.asyncio
async def test_analyze_tactical_drill_with_diagram_url():
    """analyze_tactical_drill with render_diagram=True should include URL."""
    drill_data = {"name": "Pressing Exercise"}

    with patch("src.mcp.server._api_get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _mock_response(json_data=drill_data)
        result = await analyze_tactical_drill(
            plan_id="abc-123", drill_index=1, render_diagram=True
        )

    parsed = json.loads(result)
    assert "diagram_url" in parsed
    assert "/drills/1/diagram" in parsed["diagram_url"]


@pytest.mark.asyncio
async def test_render_drill_diagram_returns_base64():
    """render_drill_diagram should return base64-encoded image data."""
    fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

    with patch("src.mcp.server._api_get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _mock_response(content=fake_png)
        result = await render_drill_diagram(plan_id="abc-123", drill_index=0)

    parsed = json.loads(result)
    assert parsed["media_type"] == "image/png"
    assert "data" in parsed
    assert parsed["size_bytes"] == len(fake_png)


@pytest.mark.asyncio
async def test_render_drill_diagram_invalid_format():
    """render_drill_diagram with invalid format should return error."""
    result = await render_drill_diagram(
        plan_id="abc-123", drill_index=0, format="svg"
    )
    parsed = json.loads(result)
    assert "error" in parsed


@pytest.mark.asyncio
async def test_search_drills_returns_results():
    """search_drills should return search results."""
    search_data = {
        "query": "counter attack",
        "results": [
            {
                "score": 0.92,
                "page_num": 1,
                "plan_id": "abc-123",
                "filename": "session.pdf",
                "plan_title": "Counter Attack Training",
            }
        ],
        "total": 1,
    }

    with patch("src.mcp.server._api_get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _mock_response(json_data=search_data)
        result = await search_drills(query="counter attack", k=3)

    parsed = json.loads(result)
    assert parsed["total"] == 1
    assert parsed["results"][0]["score"] == 0.92
    mock_get.assert_called_once_with("/api/search?q=counter%20attack&k=3")


@pytest.mark.asyncio
async def test_search_drills_not_configured():
    """search_drills should return error when service not configured."""
    with patch("src.mcp.server._api_get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _mock_response(status_code=503)
        result = await search_drills(query="pressing")

    parsed = json.loads(result)
    assert "error" in parsed
    assert "not configured" in parsed["error"]


@pytest.mark.asyncio
async def test_search_drills_service_unavailable():
    """search_drills should return error when ColPali is down."""
    with patch("src.mcp.server._api_get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _mock_response(status_code=502)
        result = await search_drills(query="rondo")

    parsed = json.loads(result)
    assert "error" in parsed
    assert "unavailable" in parsed["error"]


@pytest.mark.asyncio
async def test_export_session_pdf_returns_base64():
    """export_session_pdf should return base64-encoded PDF data."""
    fake_pdf = b"%PDF-1.4 fake content"

    with patch("src.mcp.server._api_get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _mock_response(content=fake_pdf)
        result = await export_session_pdf(plan_id="abc-123")

    parsed = json.loads(result)
    assert parsed["media_type"] == "application/pdf"
    assert "data" in parsed
    assert parsed["size_bytes"] == len(fake_pdf)
    mock_get.assert_called_once_with("/api/sessions/abc-123/export?format=pdf")


@pytest.mark.asyncio
async def test_export_session_pdf_not_found():
    """export_session_pdf should return error for unknown plan."""
    with patch("src.mcp.server._api_get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _mock_response(status_code=404)
        result = await export_session_pdf(plan_id="nonexistent")

    parsed = json.loads(result)
    assert "error" in parsed
    assert "not found" in parsed["error"]


@pytest.mark.asyncio
async def test_export_session_pdf_calls_correct_endpoint():
    """export_session_pdf should call the export endpoint with format=pdf."""
    fake_pdf = b"%PDF-1.7 test"

    with patch("src.mcp.server._api_get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _mock_response(content=fake_pdf)
        await export_session_pdf(plan_id="plan-uuid-456")

    mock_get.assert_called_once_with("/api/sessions/plan-uuid-456/export?format=pdf")
