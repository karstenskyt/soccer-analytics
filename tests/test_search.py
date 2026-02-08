"""Tests for the search route logic with mocked dependencies."""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set DATABASE_URL so Settings() can instantiate during import
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")

# Build proper FastAPI mocks before importing the search route
_fastapi_mock = MagicMock()


class _FakeHTTPException(Exception):
    """Stand-in for FastAPI's HTTPException."""

    def __init__(self, status_code, detail=""):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"{status_code}: {detail}")


# Wire up the mock so `from fastapi import HTTPException` returns our class
_fastapi_mock.HTTPException = _FakeHTTPException
_fastapi_mock.APIRouter.return_value = MagicMock(get=lambda *a, **kw: lambda fn: fn)
_fastapi_mock.Depends = lambda x: None
_fastapi_mock.Query = lambda *a, **kw: None

# Mock Docker-only modules before importing search route
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
    "sqlalchemy.ext.asyncio.session",
    "sqlalchemy.ext.asyncio.engine",
    "asyncpg",
    "mplsoccer",
    "matplotlib",
    "matplotlib.pyplot",
    "matplotlib.figure",
]
for mod in _DOCKER_ONLY_MODULES:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

# Set fastapi mock BEFORE any import of the search module
sys.modules["fastapi"] = _fastapi_mock

import httpx


def _mock_colpali_response(
    status_code: int = 200, json_data: dict | None = None
):
    """Create a mock httpx response."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data or {}
    if status_code >= 400:
        mock.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"HTTP {status_code}",
            request=MagicMock(),
            response=mock,
        )
    else:
        mock.raise_for_status.return_value = None
    return mock


# Import the actual search function (uses our mocked fastapi)
from src.api.routes.search import search_drills


@pytest.mark.asyncio
async def test_search_happy_path():
    """Search should return enriched results from ColPali."""
    mock_client = AsyncMock()
    mock_client.post.return_value = _mock_colpali_response(
        json_data={
            "results": [
                {
                    "doc_id": 0,
                    "page_num": 1,
                    "score": 0.92,
                    "plan_id": "11111111-1111-1111-1111-111111111111",
                    "filename": "session.pdf",
                }
            ],
            "query": "counter attack",
            "total": 1,
        }
    )

    mock_db = AsyncMock()

    with patch(
        "src.api.routes.search.get_session_plan",
        new_callable=AsyncMock,
    ) as mock_get_plan:
        mock_get_plan.return_value = {
            "metadata": {
                "title": "Counter Attack Training",
                "category": "Attacking",
            },
            "drills": [
                {"name": "2v1 Drill"},
                {"name": "3v2 Transition"},
            ],
        }

        result = await search_drills(
            q="counter attack", k=3, db=mock_db, colpali_client=mock_client
        )

    assert result["query"] == "counter attack"
    assert len(result["results"]) == 1
    r = result["results"][0]
    assert r["score"] == 0.92
    assert r["plan_title"] == "Counter Attack Training"
    assert r["category"] == "Attacking"
    assert "2v1 Drill" in r["drill_names"]


@pytest.mark.asyncio
async def test_search_returns_503_when_not_configured():
    """Search should raise HTTPException 503 when ColPali not configured."""
    mock_db = AsyncMock()

    with pytest.raises(_FakeHTTPException) as exc_info:
        await search_drills(q="pressing", k=5, db=mock_db, colpali_client=None)

    assert exc_info.value.status_code == 503
    assert "not configured" in exc_info.value.detail


@pytest.mark.asyncio
async def test_search_returns_502_when_service_down():
    """Search should raise HTTPException 502 when ColPali unreachable."""
    mock_client = AsyncMock()
    mock_client.post.side_effect = httpx.ConnectError("Connection refused")
    mock_db = AsyncMock()

    with pytest.raises(_FakeHTTPException) as exc_info:
        await search_drills(q="rondo", k=5, db=mock_db, colpali_client=mock_client)

    assert exc_info.value.status_code == 502
    assert "unavailable" in exc_info.value.detail


@pytest.mark.asyncio
async def test_search_without_plan_data():
    """Search should return results without enrichment if plan not found."""
    mock_client = AsyncMock()
    mock_client.post.return_value = _mock_colpali_response(
        json_data={
            "results": [
                {
                    "doc_id": 0,
                    "page_num": 0,
                    "score": 0.75,
                    "plan_id": "22222222-2222-2222-2222-222222222222",
                    "filename": "unknown.pdf",
                }
            ],
            "query": "build up",
            "total": 1,
        }
    )
    mock_db = AsyncMock()

    with patch(
        "src.api.routes.search.get_session_plan",
        new_callable=AsyncMock,
    ) as mock_get_plan:
        mock_get_plan.return_value = None

        result = await search_drills(
            q="build up", k=5, db=mock_db, colpali_client=mock_client
        )

    assert len(result["results"]) == 1
    r = result["results"][0]
    assert r["score"] == 0.75
    assert "plan_title" not in r


@pytest.mark.asyncio
async def test_search_deduplicates_plan_lookups():
    """Search should only fetch each plan_id once from the database."""
    mock_client = AsyncMock()
    mock_client.post.return_value = _mock_colpali_response(
        json_data={
            "results": [
                {
                    "doc_id": 0,
                    "page_num": 1,
                    "score": 0.9,
                    "plan_id": "11111111-1111-1111-1111-111111111111",
                    "filename": "a.pdf",
                },
                {
                    "doc_id": 0,
                    "page_num": 2,
                    "score": 0.8,
                    "plan_id": "11111111-1111-1111-1111-111111111111",
                    "filename": "a.pdf",
                },
            ],
            "query": "drill",
            "total": 2,
        }
    )
    mock_db = AsyncMock()

    with patch(
        "src.api.routes.search.get_session_plan",
        new_callable=AsyncMock,
    ) as mock_get_plan:
        mock_get_plan.return_value = {
            "metadata": {"title": "Session A"},
            "drills": [],
        }

        result = await search_drills(
            q="drill", k=10, db=mock_db, colpali_client=mock_client
        )

    assert len(result["results"]) == 2
    mock_get_plan.assert_called_once()
