"""Stage 1: PDF decomposition using Docling DocumentConverter."""

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions

logger = logging.getLogger(__name__)


@dataclass
class DecomposedDocument:
    """Result of PDF decomposition."""

    markdown: str
    images: dict[str, Path] = field(default_factory=dict)
    page_count: int = 0
    tables: list[str] = field(default_factory=list)


async def decompose_pdf(pdf_path: Path, output_dir: Path) -> DecomposedDocument:
    """Decompose a PDF into markdown text and extracted images.

    Args:
        pdf_path: Path to the input PDF file.
        output_dir: Directory to store extracted images.

    Returns:
        DecomposedDocument with markdown, images, and metadata.
    """
    logger.info(f"Decomposing PDF: {pdf_path}")
    output_dir.mkdir(parents=True, exist_ok=True)

    pipeline_options = PdfPipelineOptions(
        do_ocr=True,
        generate_picture_images=True,
        images_scale=2.0,
    )

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pipeline_options,
            )
        }
    )

    # Docling runs synchronously — offload to thread pool
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None, lambda: converter.convert(str(pdf_path))
    )

    doc = result.document

    # Export markdown
    markdown = doc.export_to_markdown()

    # Extract images from picture elements
    images: dict[str, Path] = {}
    for i, picture in enumerate(doc.pictures):
        pil_image = picture.get_image(doc)
        if pil_image is not None:
            image_path = output_dir / f"diagram_{i:03d}.png"
            pil_image.save(str(image_path))
            images[f"diagram_{i:03d}"] = image_path
            logger.info(f"Extracted image: {image_path}")

    # Extract tables
    tables = []
    for table in doc.tables:
        tables.append(table.export_to_markdown())

    page_count = doc.num_pages()

    logger.info(
        f"Decomposition complete: {len(images)} images, "
        f"{len(tables)} tables, {page_count} pages"
    )

    return DecomposedDocument(
        markdown=markdown,
        images=images,
        page_count=page_count,
        tables=tables,
    )
