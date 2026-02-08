"""FastAPI application entrypoint for Soccer Analytics Service."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .deps import engine
from .routes import drills, ingest, search, sessions

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Soccer Analytics Service starting up")
    logger.info(f"Ollama URL: {settings.ollama_url}")
    logger.info(f"VLM Model: {settings.vlm_model}")
    db_host = (
        settings.database_url.split("@")[1]
        if "@" in settings.database_url
        else "configured"
    )
    logger.info(f"Database: {db_host}")
    yield
    logger.info("Soccer Analytics Service shutting down")
    await engine.dispose()


app = FastAPI(
    title="Soccer Analytics Service",
    description=(
        "Extract, understand, and store structured information "
        "from soccer coaching PDFs."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest.router)
app.include_router(sessions.router)
app.include_router(drills.router)
app.include_router(search.router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "soccer-analytics"}


@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "service": "Soccer Analytics",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }
