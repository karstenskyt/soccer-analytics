"""PDF ingestion endpoint."""

import logging
import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.config import settings
from src.api.deps import get_db
from src.pipeline.decompose import decompose_pdf
from src.pipeline.describe import describe_diagrams
from src.pipeline.extract import extract_session_plan
from src.pipeline.validate import validate_and_enrich
from src.pipeline.store import store_session_plan

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["ingest"])


@router.post("/ingest")
async def ingest_pdf(
    file: UploadFile = File(
        ..., description="Soccer coaching PDF to process"
    ),
    db: AsyncSession = Depends(get_db),
):
    """Upload and process a soccer coaching PDF.

    Runs the full 5-stage pipeline:
    1. PDF decomposition (Docling)
    2. Diagram analysis (Qwen3-VL)
    3. Schema extraction
    4. Validation & enrichment
    5. Database storage

    Returns the extracted SessionPlan JSON.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400, detail="Only PDF files are accepted"
        )

    if file.size and file.size > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {settings.max_upload_size_mb}MB limit",
        )

    job_id = uuid4()
    upload_dir = Path(settings.upload_dir) / str(job_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = upload_dir / file.filename

    try:
        with open(pdf_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        logger.info(f"Processing PDF: {file.filename} (job: {job_id})")

        # Stage 1: Decompose PDF
        output_dir = upload_dir / "images"
        document = await decompose_pdf(pdf_path, output_dir)

        # Stage 2: Describe diagrams with VLM
        diagram_descriptions = await describe_diagrams(
            images=document.images,
            ollama_url=settings.ollama_url,
            model=settings.vlm_model,
        )

        # Stage 3: Extract structured data
        session_plan = await extract_session_plan(
            document=document,
            diagram_descriptions=diagram_descriptions,
            source_filename=file.filename,
        )

        # Stage 4: Validate and enrich
        session_plan = await validate_and_enrich(session_plan)

        # Stage 5: Store in database
        plan_id = await store_session_plan(session_plan, db)

        logger.info(f"Successfully processed {file.filename} -> {plan_id}")

        return {
            "status": "success",
            "plan_id": str(plan_id),
            "session_plan": session_plan.model_dump(mode="json"),
        }

    except Exception as e:
        logger.error(
            f"Pipeline failed for {file.filename}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=500, detail=f"Processing failed: {str(e)}"
        )
    finally:
        if pdf_path.exists():
            pdf_path.unlink()
