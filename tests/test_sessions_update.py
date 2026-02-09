"""Tests for validated PUT session endpoint."""

import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

# Ensure DATABASE_URL is set before any app module import
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")

# Mock Docker-only modules before importing app modules
_DOCKER_ONLY_MODULES = [
    "docling",
    "docling.document_converter",
    "docling.datamodel",
    "docling.datamodel.base_models",
    "docling.datamodel.pipeline_options",
    "docling_core",
    "docling_core.types",
    "docling_core.types.doc",
]
for mod in _DOCKER_ONLY_MODULES:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()


def _make_plan_dict(plan_id: str | None = None, **overrides) -> dict:
    """Build a valid SessionPlan dict for PUT body."""
    pid = plan_id or str(uuid4())
    base = {
        "id": pid,
        "metadata": {
            "title": "Updated GK Session",
            "category": "Goalkeeping",
            "difficulty": "Advanced",
            "author": "Coach Smith",
        },
        "drills": [
            {
                "id": str(uuid4()),
                "name": "2v1 Counter Attack",
                "setup": {
                    "description": "Set up cones",
                    "player_count": "6",
                    "equipment": ["cones"],
                    "area_dimensions": "30x20 yards",
                },
                "diagram": {"vlm_description": "", "player_positions": []},
                "sequence": ["Pass to striker", "Finish on goal"],
                "coaching_points": ["Timing of run"],
                "rules": [],
                "scoring": [],
                "progressions": [],
            }
        ],
        "source": {"filename": "test.pdf", "page_count": 3},
    }
    base.update(overrides)
    return base


def _get_app():
    """Create a FastAPI app with session routes."""
    from fastapi import FastAPI
    from src.api.routes.sessions import router

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client():
    """Create a test client with mocked DB dependency."""
    app = _get_app()

    from starlette.testclient import TestClient
    from src.api.deps import get_db

    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_put_invalid_body_returns_422(client):
    """PUT with invalid body should return 422 validation error."""
    plan_id = str(uuid4())
    # Missing required 'metadata' and 'source' fields
    response = client.put(
        f"/api/sessions/{plan_id}",
        json={"drills": []},
    )
    assert response.status_code == 422


def test_put_invalid_uuid_returns_422(client):
    """PUT with invalid UUID should return 422."""
    response = client.put(
        "/api/sessions/not-a-uuid",
        json=_make_plan_dict(),
    )
    assert response.status_code == 422


@patch("src.api.routes.sessions.replace_session_plan", new_callable=AsyncMock)
@patch("src.api.routes.sessions.validate_and_enrich", new_callable=AsyncMock)
@patch("src.api.routes.sessions.get_session_plan", new_callable=AsyncMock)
def test_put_nonexistent_plan_returns_404(
    mock_get, mock_enrich, mock_replace, client
):
    """PUT to nonexistent plan_id should return 404."""
    mock_get.return_value = None
    plan_id = str(uuid4())
    body = _make_plan_dict(plan_id)

    response = client.put(f"/api/sessions/{plan_id}", json=body)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@patch("src.api.routes.sessions.replace_session_plan", new_callable=AsyncMock)
@patch("src.api.routes.sessions.validate_and_enrich", new_callable=AsyncMock)
@patch("src.api.routes.sessions.get_session_plan", new_callable=AsyncMock)
def test_put_valid_body_returns_enriched(
    mock_get, mock_enrich, mock_replace, client
):
    """PUT with valid body should return enriched plan."""
    plan_id = str(uuid4())
    body = _make_plan_dict(plan_id)

    # Simulate existing plan
    mock_get.return_value = body

    # Simulate enrichment: the plan comes back unchanged
    mock_enrich.side_effect = lambda plan: plan
    mock_replace.return_value = None

    response = client.put(f"/api/sessions/{plan_id}", json=body)
    assert response.status_code == 200
    result = response.json()
    assert result["id"] == plan_id
    assert result["metadata"]["title"] == "Updated GK Session"
    assert len(result["drills"]) == 1


@patch("src.api.routes.sessions.replace_session_plan", new_callable=AsyncMock)
@patch("src.api.routes.sessions.validate_and_enrich", new_callable=AsyncMock)
@patch("src.api.routes.sessions.get_session_plan", new_callable=AsyncMock)
def test_put_body_id_overridden_by_url(
    mock_get, mock_enrich, mock_replace, client
):
    """Body ID should be overridden by URL plan_id."""
    url_plan_id = str(uuid4())
    body_plan_id = str(uuid4())
    body = _make_plan_dict(body_plan_id)

    mock_get.return_value = body
    mock_enrich.side_effect = lambda plan: plan
    mock_replace.return_value = None

    response = client.put(f"/api/sessions/{url_plan_id}", json=body)
    assert response.status_code == 200
    result = response.json()
    # The returned ID should match the URL, not the body
    assert result["id"] == url_plan_id


@patch("src.api.routes.sessions.replace_session_plan", new_callable=AsyncMock)
@patch("src.api.routes.sessions.validate_and_enrich", new_callable=AsyncMock)
@patch("src.api.routes.sessions.get_session_plan", new_callable=AsyncMock)
def test_put_calls_enrich_and_replace(
    mock_get, mock_enrich, mock_replace, client
):
    """PUT should call validate_and_enrich and replace_session_plan."""
    plan_id = str(uuid4())
    body = _make_plan_dict(plan_id)

    mock_get.return_value = body
    mock_enrich.side_effect = lambda plan: plan
    mock_replace.return_value = None

    response = client.put(f"/api/sessions/{plan_id}", json=body)
    assert response.status_code == 200

    mock_enrich.assert_called_once()
    mock_replace.assert_called_once()
    # Verify plan_id was passed to replace
    call_args = mock_replace.call_args
    from uuid import UUID
    assert call_args[0][0] == UUID(plan_id)
