"""PDF ingestion endpoint."""

import logging
import shutil
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.config import settings
from src.api.deps import get_colpali_client, get_db
from src.pipeline.decompose import decompose_pdf
from src.pipeline.describe import describe_diagrams, extract_all_positions
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
    colpali_client: httpx.AsyncClient | None = Depends(get_colpali_client),
):
    """Upload and process a soccer coaching PDF.

    Runs the full 6-stage pipeline:
    1. PDF decomposition (Docling)
    2. Diagram analysis (Qwen3-VL)
    3. Schema extraction
    4. Validation & enrichment
    5. Database storage
    6. ColPali visual indexing (best-effort)

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
    safe_filename = Path(file.filename).name  # strip directory components
    pdf_path = upload_dir / safe_filename

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

        # Stage 2b: Focused position extraction (second VLM pass)
        if settings.extract_positions:
            position_data = await extract_all_positions(
                images=document.images,
                diagram_descriptions=diagram_descriptions,
                ollama_url=settings.ollama_url,
                model=settings.vlm_model,
            )
            for key, positions in position_data.items():
                if key in diagram_descriptions and positions:
                    diagram_descriptions[key]["player_positions"] = positions

        # Stage 3: Extract structured data
        session_plan = await extract_session_plan(
            document=document,
            diagram_descriptions=diagram_descriptions,
            source_filename=safe_filename,
        )

        # Stage 4: Validate and enrich
        session_plan = await validate_and_enrich(session_plan)

        # Stage 5: Store in database
        plan_id = await store_session_plan(session_plan, db)

        # Stage 6: Index in ColPali for visual retrieval (best-effort)
        indexed = False
        if colpali_client is not None:
            try:
                resp = await colpali_client.post(
                    "/index",
                    json={
                        "pdf_path": str(pdf_path),
                        "plan_id": str(plan_id),
                        "filename": safe_filename,
                    },
                )
                resp.raise_for_status()
                indexed = True
                logger.info(f"Indexed {safe_filename} in ColPali")
            except Exception as idx_err:
                logger.warning(
                    f"ColPali indexing failed (non-fatal): {idx_err}"
                )

        logger.info(f"Successfully processed {file.filename} -> {plan_id}")

        return {
            "status": "success",
            "plan_id": str(plan_id),
            "indexed": indexed,
            "session_plan": session_plan.model_dump(mode="json"),
        }

    except Exception as e:
        logger.error(
            f"Pipeline failed for {file.filename}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=500, detail="Processing failed. Check server logs for details."
        )
    finally:
        if upload_dir.exists():
            shutil.rmtree(upload_dir, ignore_errors=True)
