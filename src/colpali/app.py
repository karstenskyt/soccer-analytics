"""Internal FastAPI service for ColPali visual retrieval."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .index_manager import IndexManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

manager = IndexManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the ColPali model on startup."""
    logger.info("ColPali service starting — loading model...")
    manager.load()
    logger.info("ColPali model loaded successfully")
    yield
    logger.info("ColPali service shutting down")


app = FastAPI(
    title="ColPali Visual Retrieval Service",
    version="0.1.0",
    lifespan=lifespan,
)


class IndexRequest(BaseModel):
    pdf_path: str
    plan_id: str
    filename: str


class IndexResponse(BaseModel):
    doc_id: int
    plan_id: str
    indexed: bool


class SearchRequest(BaseModel):
    query: str
    k: int = 5


class SearchResult(BaseModel):
    doc_id: int
    page_num: int
    score: float
    plan_id: str | None
    filename: str | None


class SearchResponse(BaseModel):
    results: list[SearchResult]
    query: str
    total: int


@app.post("/index", response_model=IndexResponse)
async def index_document(request: IndexRequest):
    """Index a PDF document for visual retrieval."""
    try:
        doc_id = manager.index_document(
            pdf_path=request.pdf_path,
            plan_id=request.plan_id,
            filename=request.filename,
        )
        return IndexResponse(
            doc_id=doc_id,
            plan_id=request.plan_id,
            indexed=True,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="PDF file not found")
    except Exception as e:
        logger.error(f"Indexing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """Search indexed documents with a text query."""
    try:
        results = manager.search(query=request.query, k=request.k)
        return SearchResponse(
            results=results,
            query=request.query,
            total=len(results),
        )
    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy" if manager.is_loaded else "loading",
        "service": "colpali",
        "doc_count": manager.doc_count,
    }
