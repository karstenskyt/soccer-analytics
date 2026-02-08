"""Tests for ColPali IndexManager with mocked byaldi."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Mock byaldi (not installed locally, Docker-only dependency)
_byaldi_mock = MagicMock()
sys.modules["byaldi"] = _byaldi_mock


@pytest.fixture
def tmp_index_dir(tmp_path):
    """Create a temporary index directory."""
    return tmp_path / "colpali_index"


@pytest.fixture
def mock_settings(tmp_index_dir):
    """Patch ColPali settings to use temp directory."""
    with patch("src.colpali.index_manager.settings") as mock_s:
        mock_s.index_root = str(tmp_index_dir)
        mock_s.index_name = "test_index"
        mock_s.model_name = "vidore/colqwen2-v1.0"
        yield mock_s


@pytest.fixture
def mock_model():
    """Create a mock RAGMultiModalModel."""
    model = MagicMock()
    model.index.return_value = None
    model.add_to_index.return_value = None
    model.search.return_value = []
    return model


@pytest.fixture
def manager(mock_settings, mock_model):
    """Create an IndexManager with mocked dependencies."""
    with patch(
        "src.colpali.index_manager.RAGMultiModalModel"
    ) as MockRAG:
        MockRAG.from_pretrained.return_value = mock_model
        MockRAG.from_index.return_value = mock_model

        from src.colpali.index_manager import IndexManager

        mgr = IndexManager()
        yield mgr, MockRAG, mock_model


class TestIndexManagerLoad:
    """Tests for loading the index."""

    def test_load_pretrained_when_no_index_exists(self, manager):
        """Should load pretrained model when no index on disk."""
        mgr, MockRAG, mock_model = manager
        mgr.load()

        MockRAG.from_pretrained.assert_called_once_with(
            "vidore/colqwen2-v1.0", verbose=1
        )
        assert mgr.is_loaded
        assert mgr.doc_count == 0

    def test_load_existing_index(self, manager, tmp_index_dir):
        """Should load from index when directory exists with files."""
        mgr, MockRAG, mock_model = manager
        index_path = tmp_index_dir / "test_index"
        index_path.mkdir(parents=True)
        (index_path / "index.faiss").write_text("fake")

        mgr.load()

        MockRAG.from_index.assert_called_once()
        assert mgr.is_loaded

    def test_load_restores_doc_mapping(self, manager, tmp_index_dir):
        """Should restore doc_mapping from disk on load."""
        mgr, MockRAG, mock_model = manager
        tmp_index_dir.mkdir(parents=True)
        mapping = {
            "0": {"plan_id": "abc-123", "filename": "session.pdf"},
            "1": {"plan_id": "def-456", "filename": "training.pdf"},
        }
        (tmp_index_dir / "doc_mapping.json").write_text(json.dumps(mapping))

        mgr.load()

        assert mgr.doc_count == 2


class TestIndexManagerIndex:
    """Tests for indexing documents."""

    def test_index_first_document_creates_index(self, manager, tmp_path):
        """First document should call model.index()."""
        mgr, MockRAG, mock_model = manager
        mgr.load()

        pdf = tmp_path / "test.pdf"
        pdf.write_text("fake pdf")

        doc_id = mgr.index_document(
            pdf_path=str(pdf),
            plan_id="abc-123",
            filename="test.pdf",
        )

        assert doc_id == 0
        mock_model.index.assert_called_once()
        assert mgr.doc_count == 1

    def test_index_subsequent_document_adds_to_index(
        self, manager, tmp_path
    ):
        """Subsequent documents should call model.add_to_index()."""
        mgr, MockRAG, mock_model = manager
        mgr.load()

        pdf1 = tmp_path / "first.pdf"
        pdf1.write_text("fake pdf")
        mgr.index_document(str(pdf1), "abc-123", "first.pdf")

        pdf2 = tmp_path / "second.pdf"
        pdf2.write_text("fake pdf 2")
        doc_id = mgr.index_document(str(pdf2), "def-456", "second.pdf")

        assert doc_id == 1
        mock_model.add_to_index.assert_called_once()
        assert mgr.doc_count == 2

    def test_index_saves_mapping(self, manager, tmp_path, tmp_index_dir):
        """Indexing should persist doc_mapping.json."""
        mgr, MockRAG, mock_model = manager
        mgr.load()

        pdf = tmp_path / "test.pdf"
        pdf.write_text("fake pdf")
        mgr.index_document(str(pdf), "abc-123", "test.pdf")

        mapping_path = tmp_index_dir / "doc_mapping.json"
        assert mapping_path.exists()
        mapping = json.loads(mapping_path.read_text())
        assert "0" in mapping
        assert mapping["0"]["plan_id"] == "abc-123"

    def test_index_raises_if_not_loaded(self, manager, tmp_path):
        """Should raise RuntimeError if load() not called."""
        mgr, MockRAG, mock_model = manager

        with pytest.raises(RuntimeError, match="not loaded"):
            mgr.index_document(str(tmp_path / "x.pdf"), "abc", "x.pdf")


class TestIndexManagerSearch:
    """Tests for searching the index."""

    def test_search_empty_index_returns_empty(self, manager):
        """Search on empty index should return empty list."""
        mgr, MockRAG, mock_model = manager
        mgr.load()

        results = mgr.search("counter attack", k=3)
        assert results == []

    def test_search_with_dict_results(self, manager, tmp_path):
        """Should handle search results as dicts."""
        mgr, MockRAG, mock_model = manager
        mgr.load()

        pdf = tmp_path / "test.pdf"
        pdf.write_text("fake")
        mgr.index_document(str(pdf), "abc-123", "test.pdf")

        mock_model.search.return_value = [
            {"doc_id": 0, "page_num": 1, "score": 0.95}
        ]

        results = mgr.search("pressing drill", k=3)
        assert len(results) == 1
        assert results[0]["plan_id"] == "abc-123"
        assert results[0]["score"] == 0.95
        assert results[0]["page_num"] == 1

    def test_search_with_object_results(self, manager, tmp_path):
        """Should handle search results as objects with attributes."""
        mgr, MockRAG, mock_model = manager
        mgr.load()

        pdf = tmp_path / "test.pdf"
        pdf.write_text("fake")
        mgr.index_document(str(pdf), "abc-123", "test.pdf")

        class FakeResult:
            """Non-dict result object (byaldi Result)."""
            def __init__(self, doc_id, page_num, score):
                self.doc_id = doc_id
                self.page_num = page_num
                self.score = score

        mock_model.search.return_value = [FakeResult(0, 2, 0.87)]

        results = mgr.search("rondo exercise", k=1)
        assert len(results) == 1
        assert results[0]["plan_id"] == "abc-123"
        assert results[0]["score"] == 0.87

    def test_search_unknown_doc_id_returns_none_mapping(
        self, manager, tmp_path
    ):
        """Results with unknown doc_id should have None plan_id/filename."""
        mgr, MockRAG, mock_model = manager
        mgr.load()

        pdf = tmp_path / "test.pdf"
        pdf.write_text("fake")
        mgr.index_document(str(pdf), "abc-123", "test.pdf")

        mock_model.search.return_value = [
            {"doc_id": 99, "page_num": 0, "score": 0.5}
        ]

        results = mgr.search("unknown", k=1)
        assert len(results) == 1
        assert results[0]["plan_id"] is None
        assert results[0]["filename"] is None

    def test_search_raises_if_not_loaded(self, manager):
        """Should raise RuntimeError if load() not called."""
        mgr, MockRAG, mock_model = manager

        with pytest.raises(RuntimeError, match="not loaded"):
            mgr.search("query")
