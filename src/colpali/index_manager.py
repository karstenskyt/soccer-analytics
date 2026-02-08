"""Manages byaldi FAISS index lifecycle and doc_id-to-plan_id mapping."""

import json
import logging
import threading
from pathlib import Path

from byaldi import RAGMultiModalModel

from .config import settings

logger = logging.getLogger(__name__)


class IndexManager:
    """Thread-safe singleton managing the ColPali/byaldi index."""

    def __init__(self) -> None:
        self._model: RAGMultiModalModel | None = None
        self._lock = threading.Lock()
        self._doc_count = 0
        self._index_root = Path(settings.index_root)
        self._index_name = settings.index_name
        self._mapping_path = self._index_root / "doc_mapping.json"
        self._doc_mapping: dict[int, dict] = {}

    def load(self) -> None:
        """Load existing index from disk or initialize pretrained model."""
        index_path = self._index_root / self._index_name
        if index_path.exists() and any(index_path.iterdir()):
            logger.info(f"Loading existing index from {index_path}")
            self._model = RAGMultiModalModel.from_index(
                str(index_path),
                verbose=1,
            )
        else:
            logger.info(
                f"No existing index found, loading pretrained: {settings.model_name}"
            )
            self._model = RAGMultiModalModel.from_pretrained(
                settings.model_name,
                verbose=1,
            )
        self._load_mapping()
        self._doc_count = len(self._doc_mapping)
        logger.info(
            f"Index ready with {self._doc_count} documents"
        )

    def _load_mapping(self) -> None:
        """Load doc_id-to-plan mapping from disk."""
        if self._mapping_path.exists():
            raw = json.loads(self._mapping_path.read_text())
            self._doc_mapping = {int(k): v for k, v in raw.items()}
        else:
            self._doc_mapping = {}

    def _save_mapping(self) -> None:
        """Persist doc_id-to-plan mapping to disk."""
        self._mapping_path.parent.mkdir(parents=True, exist_ok=True)
        self._mapping_path.write_text(
            json.dumps(self._doc_mapping, indent=2)
        )

    def index_document(
        self, pdf_path: str, plan_id: str, filename: str
    ) -> int:
        """Index a PDF document into the FAISS index.

        Args:
            pdf_path: Absolute path to the PDF file.
            plan_id: UUID of the session plan.
            filename: Original filename for display.

        Returns:
            Number of pages indexed.
        """
        with self._lock:
            if self._model is None:
                raise RuntimeError("Index not loaded. Call load() first.")

            if self._doc_count == 0:
                logger.info(f"Creating new index with {filename}")
                self._model.index(
                    input_path=pdf_path,
                    index_name=self._index_name,
                    store_collection_with_index=False,
                    overwrite=False,
                )
            else:
                logger.info(f"Adding {filename} to existing index")
                self._model.add_to_index(
                    input_item=pdf_path,
                    store_collection_with_index=False,
                )

            doc_id = self._doc_count
            self._doc_mapping[doc_id] = {
                "plan_id": plan_id,
                "filename": filename,
            }
            self._doc_count += 1
            self._save_mapping()

            logger.info(
                f"Indexed {filename} as doc_id={doc_id} for plan {plan_id}"
            )
            return doc_id

    def search(self, query: str, k: int = 5) -> list[dict]:
        """Search the index with a text query.

        Args:
            query: Natural language search query.
            k: Number of results to return.

        Returns:
            List of result dicts with doc_id, page_num, score, plan_id, filename.
        """
        with self._lock:
            if self._model is None:
                raise RuntimeError("Index not loaded. Call load() first.")

            if self._doc_count == 0:
                return []

            raw_results = self._model.search(query, k=k)

        results = []
        for item in raw_results:
            if isinstance(item, dict):
                doc_id = item.get("doc_id", 0)
                page_num = item.get("page_num", 0)
                score = item.get("score", 0.0)
            else:
                doc_id = getattr(item, "doc_id", 0)
                page_num = getattr(item, "page_num", 0)
                score = getattr(item, "score", 0.0)

            mapping = self._doc_mapping.get(doc_id, {})
            results.append({
                "doc_id": doc_id,
                "page_num": page_num,
                "score": float(score),
                "plan_id": mapping.get("plan_id"),
                "filename": mapping.get("filename"),
            })

        return results

    @property
    def doc_count(self) -> int:
        """Number of indexed documents."""
        return self._doc_count

    @property
    def is_loaded(self) -> bool:
        """Whether the model has been loaded."""
        return self._model is not None
