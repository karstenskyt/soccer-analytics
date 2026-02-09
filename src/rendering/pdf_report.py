"""Generate professional coaching PDF reports from session plans."""

import io
import logging
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from src.schemas.session_plan import DrillBlock, SessionPlan

logger = logging.getLogger(__name__)

# Color palette
DARK_BLUE = colors.HexColor("#1a237e")
GREEN = colors.HexColor("#2e7d32")
LIGHT_GREY = colors.HexColor("#f5f5f5")
WHITE = colors.white


def _build_styles() -> dict[str, ParagraphStyle]:
    """Build the custom paragraph styles for the PDF."""
    base = getSampleStyleSheet()
    return {
        "cover_title": ParagraphStyle(
            "CoverTitle",
            parent=base["Title"],
            fontSize=28,
            leading=34,
            textColor=DARK_BLUE,
            alignment=1,  # center
            spaceAfter=20,
        ),
        "cover_subtitle": ParagraphStyle(
            "CoverSubtitle",
            parent=base["Normal"],
            fontSize=14,
            leading=18,
            textColor=colors.grey,
            alignment=1,
            spaceAfter=8,
        ),
        "toc_heading": ParagraphStyle(
            "TOCHeading",
            parent=base["Heading1"],
            fontSize=20,
            textColor=DARK_BLUE,
            spaceAfter=20,
        ),
        "drill_title": ParagraphStyle(
            "DrillTitle",
            parent=base["Heading1"],
            fontSize=18,
            leading=22,
            textColor=DARK_BLUE,
            spaceAfter=12,
        ),
        "section_heading": ParagraphStyle(
            "SectionHeading",
            parent=base["Heading2"],
            fontSize=12,
            leading=15,
            textColor=DARK_BLUE,
            spaceAfter=6,
            spaceBefore=10,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["Normal"],
            fontSize=10,
            leading=13,
            spaceAfter=4,
        ),
        "bullet": ParagraphStyle(
            "Bullet",
            parent=base["Normal"],
            fontSize=10,
            leading=13,
            leftIndent=15,
            spaceAfter=2,
        ),
        "tactical_label": ParagraphStyle(
            "TacticalLabel",
            parent=base["Normal"],
            fontSize=9,
            leading=12,
            textColor=WHITE,
            fontName="Helvetica-Bold",
        ),
        "tactical_value": ParagraphStyle(
            "TacticalValue",
            parent=base["Normal"],
            fontSize=9,
            leading=12,
            textColor=WHITE,
        ),
    }


def _header_footer(canvas, doc):
    """Draw header and footer on content pages."""
    canvas.saveState()
    # Header: session title left
    if hasattr(doc, "session_title"):
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.grey)
        canvas.drawString(2 * cm, A4[1] - 1.2 * cm, doc.session_title)
    # Footer: page number right
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.grey)
    canvas.drawRightString(
        A4[0] - 2 * cm, 1.2 * cm, f"Page {doc.page}"
    )
    canvas.restoreState()


def _cover_header_footer(canvas, doc):
    """No header/footer on cover page."""
    pass


def _build_cover_page(plan: SessionPlan, styles: dict) -> list:
    """Build the cover page flowables."""
    elements = []
    elements.append(Spacer(1, 6 * cm))
    elements.append(
        Paragraph(plan.metadata.title, styles["cover_title"])
    )
    elements.append(Spacer(1, 1 * cm))

    if plan.metadata.author:
        elements.append(
            Paragraph(f"Author: {plan.metadata.author}", styles["cover_subtitle"])
        )
    if plan.metadata.category:
        elements.append(
            Paragraph(f"Category: {plan.metadata.category}", styles["cover_subtitle"])
        )
    if plan.metadata.difficulty:
        elements.append(
            Paragraph(
                f"Difficulty: {plan.metadata.difficulty}", styles["cover_subtitle"]
            )
        )
    if plan.metadata.duration_minutes:
        elements.append(
            Paragraph(
                f"Duration: {plan.metadata.duration_minutes} minutes",
                styles["cover_subtitle"],
            )
        )

    elements.append(Spacer(1, 2 * cm))
    elements.append(
        Paragraph(
            f"{len(plan.drills)} Drill{'s' if len(plan.drills) != 1 else ''}",
            styles["cover_subtitle"],
        )
    )
    elements.append(
        Paragraph(
            f"Generated: {datetime.now().strftime('%Y-%m-%d')}",
            styles["cover_subtitle"],
        )
    )

    elements.append(NextPageTemplate("content"))
    elements.append(PageBreak())
    return elements


def _build_toc(plan: SessionPlan, styles: dict) -> list:
    """Build the table of contents page."""
    elements = []
    elements.append(Paragraph("Table of Contents", styles["toc_heading"]))
    elements.append(Spacer(1, 0.5 * cm))

    for i, drill in enumerate(plan.drills, 1):
        elements.append(
            Paragraph(
                f"{i}. {drill.name}",
                styles["body"],
            )
        )

    if not plan.drills:
        elements.append(Paragraph("No drills in this session plan.", styles["body"]))

    elements.append(PageBreak())
    return elements


def _build_tactical_box(drill: DrillBlock, styles: dict) -> list:
    """Build the tactical context box for a drill."""
    tc = drill.tactical_context
    if not tc:
        return []

    rows = []
    if tc.methodology:
        rows.append([
            Paragraph("Methodology", styles["tactical_label"]),
            Paragraph(tc.methodology, styles["tactical_value"]),
        ])
    if tc.game_element:
        rows.append([
            Paragraph("Game Element", styles["tactical_label"]),
            Paragraph(tc.game_element.value, styles["tactical_value"]),
        ])
    if tc.lanes:
        lane_str = ", ".join(lane.value.replace("_", " ").title() for lane in tc.lanes)
        rows.append([
            Paragraph("Lanes", styles["tactical_label"]),
            Paragraph(lane_str, styles["tactical_value"]),
        ])
    if tc.situation_type:
        rows.append([
            Paragraph("Situation Type", styles["tactical_label"]),
            Paragraph(tc.situation_type.value, styles["tactical_value"]),
        ])
    if tc.phase_of_play:
        rows.append([
            Paragraph("Phase of Play", styles["tactical_label"]),
            Paragraph(tc.phase_of_play, styles["tactical_value"]),
        ])
    if tc.numerical_advantage:
        rows.append([
            Paragraph("Numerical Advantage", styles["tactical_label"]),
            Paragraph(tc.numerical_advantage, styles["tactical_value"]),
        ])

    if not rows:
        return []

    elements = []
    elements.append(Spacer(1, 0.3 * cm))
    elements.append(Paragraph("Tactical Context", styles["section_heading"]))

    table = Table(rows, colWidths=[5 * cm, 11 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GREEN),
        ("TEXTCOLOR", (0, 0), (-1, -1), WHITE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [GREEN, colors.HexColor("#388e3c")]),
    ]))
    elements.append(table)
    return elements


def _render_drill_diagram_png(drill: DrillBlock) -> bytes | None:
    """Render a drill's pitch diagram to PNG bytes, or None on failure."""
    try:
        from src.rendering.pitch import render_drill_diagram

        return render_drill_diagram(drill, fmt="png")
    except Exception:
        logger.warning(f"Failed to render diagram for drill '{drill.name}'", exc_info=True)
        return None


def _build_drill_page(
    drill: DrillBlock, index: int, styles: dict
) -> list:
    """Build a single drill page."""
    elements = []
    elements.append(
        Paragraph(f"Drill {index + 1}: {drill.name}", styles["drill_title"])
    )

    # Pitch diagram
    png_bytes = _render_drill_diagram_png(drill)
    if png_bytes:
        img = Image(io.BytesIO(png_bytes), width=16 * cm, height=11.2 * cm)
        elements.append(img)
        elements.append(Spacer(1, 0.3 * cm))

    # Setup table
    setup = drill.setup
    setup_rows = []
    if setup.description:
        setup_rows.append(["Description", setup.description])
    if setup.player_count:
        setup_rows.append(["Players", setup.player_count])
    if setup.equipment:
        setup_rows.append(["Equipment", ", ".join(setup.equipment)])
    if setup.area_dimensions:
        setup_rows.append(["Area", setup.area_dimensions])

    if setup_rows:
        elements.append(Paragraph("Setup", styles["section_heading"]))
        table = Table(setup_rows, colWidths=[4 * cm, 12 * cm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), LIGHT_GREY),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ]))
        elements.append(table)

    # Sequence
    if drill.sequence:
        elements.append(Paragraph("Sequence", styles["section_heading"]))
        for i, step in enumerate(drill.sequence, 1):
            elements.append(
                Paragraph(f"{i}. {step}", styles["bullet"])
            )

    # Coaching points
    if drill.coaching_points:
        elements.append(Paragraph("Coaching Points", styles["section_heading"]))
        for point in drill.coaching_points:
            elements.append(
                Paragraph(f"\u2022 {point}", styles["bullet"])
            )

    # Rules
    if drill.rules:
        elements.append(Paragraph("Rules", styles["section_heading"]))
        for rule in drill.rules:
            elements.append(
                Paragraph(f"\u2022 {rule}", styles["bullet"])
            )

    # Scoring
    if drill.scoring:
        elements.append(Paragraph("Scoring", styles["section_heading"]))
        for score in drill.scoring:
            elements.append(
                Paragraph(f"\u2022 {score}", styles["bullet"])
            )

    # Progressions
    if drill.progressions:
        elements.append(Paragraph("Progressions", styles["section_heading"]))
        for prog in drill.progressions:
            elements.append(
                Paragraph(f"\u2022 {prog}", styles["bullet"])
            )

    # Tactical context box
    elements.extend(_build_tactical_box(drill, styles))

    elements.append(PageBreak())
    return elements


def generate_session_pdf(session_plan: SessionPlan) -> bytes:
    """Generate a professional coaching PDF from a session plan.

    Args:
        session_plan: Complete session plan with drills.

    Returns:
        PDF file bytes.
    """
    buf = io.BytesIO()
    styles = _build_styles()

    # Define frames
    cover_frame = Frame(
        2 * cm, 2 * cm, A4[0] - 4 * cm, A4[1] - 4 * cm, id="cover"
    )
    content_frame = Frame(
        2 * cm, 2 * cm, A4[0] - 4 * cm, A4[1] - 4 * cm, id="content"
    )

    doc = BaseDocTemplate(
        buf,
        pagesize=A4,
        title=session_plan.metadata.title,
        author=session_plan.metadata.author or "",
    )
    doc.session_title = session_plan.metadata.title

    doc.addPageTemplates([
        PageTemplate(
            id="cover",
            frames=[cover_frame],
            onPage=_cover_header_footer,
        ),
        PageTemplate(
            id="content",
            frames=[content_frame],
            onPage=_header_footer,
        ),
    ])

    # Build story
    story = []
    story.extend(_build_cover_page(session_plan, styles))
    story.extend(_build_toc(session_plan, styles))

    for i, drill in enumerate(session_plan.drills):
        story.extend(_build_drill_page(drill, i, styles))

    doc.multiBuild(story)
    buf.seek(0)
    return buf.read()
