"""Stage 3: Extract structured SessionPlan from decomposed content."""

import logging
import re
from pathlib import Path

from src.schemas.session_plan import (
    SessionPlan,
    SessionMetadata,
    DrillBlock,
    DrillSetup,
    DiagramInfo,
    PlayerPosition,
    Source,
)
from .decompose import DecomposedDocument

logger = logging.getLogger(__name__)

# Sub-section headers that belong WITHIN a drill (not drill names themselves).
# These patterns are matched case-insensitively against ## headers.
_SUBSECTION_PATTERNS = [
    r"^setup(?:\s+and\s+organization)?[:\s]*$",
    r"^organization[:\s]*$",
    r"^sequence[:\s]*$",
    r"^process(?:\s+and\s+objectives)?[:\s]*$",
    r"^objectives?[:\s]*$",
    r"^execution[:\s]*$",
    r"^procedure[:\s]*$",
    r"^progressions?[:\s]*$",
    r"^variations?[:\s]*$",
    r"^coaching\s+(?:points?|tips?|notes?|tasks?)[:\s]*$",
    r"^key\s+points?[:\s]*$",
    r"^rules?[:\s]*$",
    r"^constraints?[:\s]*$",
    r"^scoring[:\s]*$",
    r"^points?[:\s]*$",
    r"^equipment[:\s]*$",
    r"^materials?[:\s]*$",
]

# Headers that are book structure, NOT drills. Skip these entirely.
_NON_DRILL_PATTERNS = [
    r"^(?:part\s+(?:one|two|three|four|five|six|\d+))$",
    r"^authors?$",
    r"^acknowledgment[s]?$",
    r"^content[s]?$",
    r"^table\s+of\s+contents?$",
    r"^introduction$",
    r"^foreword$",
    r"^preface$",
    r"^bibliography$",
    r"^references$",
    r"^index$",
    r"^appendix$",
    r"^glossary$",
]

_SUBSECTION_RE = re.compile(
    "|".join(_SUBSECTION_PATTERNS), re.IGNORECASE
)
_NON_DRILL_RE = re.compile(
    "|".join(_NON_DRILL_PATTERNS), re.IGNORECASE
)


def _is_subsection_header(header_text: str) -> bool:
    """Check if a header is a drill sub-section (Setup, Sequence, etc.)."""
    return bool(_SUBSECTION_RE.match(header_text.strip()))


def _is_non_drill_header(header_text: str) -> bool:
    """Check if a header is book structure (AUTHORS, PART ONE, etc.)."""
    return bool(_NON_DRILL_RE.match(header_text.strip()))


def _classify_subsection(header_text: str) -> str:
    """Classify a sub-section header into a canonical field name."""
    h = header_text.strip().lower().rstrip(":")
    if re.match(r"setup|organization", h):
        return "setup"
    if re.match(r"sequence|execution|procedure|process", h):
        return "sequence"
    if re.match(r"progression|variation|advance", h):
        return "progressions"
    if re.match(r"coaching|key\s+point", h):
        return "coaching_points"
    if re.match(r"rule|constraint", h):
        return "rules"
    if re.match(r"scoring|points?$", h):
        return "scoring"
    if re.match(r"equipment|material", h):
        return "equipment"
    if re.match(r"objective", h):
        return "sequence"  # Objectives map to sequence/process
    return "setup"


def _parse_player_positions(positions_data: list[dict]) -> list[PlayerPosition]:
    """Convert VLM position data to PlayerPosition models."""
    result = []
    for pos in positions_data:
        try:
            result.append(
                PlayerPosition(
                    label=str(pos.get("label", "Unknown")),
                    x=float(pos.get("x", 50)),
                    y=float(pos.get("y", 50)),
                    role=pos.get("role"),
                )
            )
        except (ValueError, TypeError) as e:
            logger.warning(f"Skipping invalid position: {pos} - {e}")
    return result


def _extract_list_items(text: str) -> list[str]:
    """Extract bulleted/numbered list items from a text block."""
    items = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        # Skip HTML comments (<!-- image --> markers from Docling)
        if line.startswith("<!--"):
            continue
        # Strip bullet/number prefix
        cleaned = re.sub(r"^[-*\d.()]+\s+", "", line).strip()
        if cleaned and len(cleaned) > 2:
            # Skip page numbers (bare digits)
            if cleaned.isdigit():
                continue
            # Skip image markers that survived cleaning
            if "<!-- image -->" in cleaned:
                cleaned = cleaned.replace("<!-- image -->", "").strip()
                if not cleaned:
                    continue
            items.append(cleaned)
    return items


def _extract_body_text(text: str) -> str:
    """Extract body text, removing list markers and image comments."""
    lines = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        # Skip HTML comments
        if line.startswith("<!--"):
            continue
        # Skip page numbers
        if line.isdigit():
            continue
        cleaned = re.sub(r"^[-*\d.()]+\s+", "", line).strip()
        # Remove inline image markers
        cleaned = cleaned.replace("<!-- image -->", "").strip()
        if cleaned:
            lines.append(cleaned)
    return "\n".join(lines)


def _split_into_header_sections(markdown: str) -> list[tuple[str, str]]:
    """Split markdown into (header_text, body_text) pairs.

    Returns list of tuples where header_text is the ## header content
    and body_text is everything until the next ## header.
    The first entry may have an empty header (content before first ##).
    """
    sections = []
    lines = markdown.split("\n")
    current_header = ""
    current_body_lines = []

    for line in lines:
        header_match = re.match(r"^#{2,3}\s+(.+)$", line)
        if header_match:
            # Save previous section
            if current_header or current_body_lines:
                sections.append(
                    (current_header, "\n".join(current_body_lines))
                )
            current_header = header_match.group(1).strip()
            current_body_lines = []
        else:
            current_body_lines.append(line)

    # Save last section
    if current_header or current_body_lines:
        sections.append((current_header, "\n".join(current_body_lines)))

    return sections


def _find_image_for_section(
    section_text: str,
    image_keys: list[str],
    used_images: set[str],
) -> str | None:
    """Find the next unused image that appears in or near this section."""
    # Check if section contains <!-- image --> marker
    if "<!-- image -->" in section_text:
        for key in image_keys:
            if key not in used_images:
                return key
    return None


def _group_drill_sections(
    sections: list[tuple[str, str]],
) -> list[dict]:
    """Group ## headers into drills with their sub-sections.

    A drill starts with a header that is NOT a sub-section header and NOT
    a non-drill header. Sub-section headers that follow are grouped under it.

    Returns list of dicts:
    {
        'name': str,
        'body': str,           # Body text directly under the drill header
        'subsections': {       # Keyed by canonical field name
            'setup': str,
            'sequence': str,
            ...
        },
        'all_text': str,       # Combined text for this drill group
    }
    """
    drills = []
    current_drill = None

    for header, body in sections:
        if not header:
            # Pre-header content (metadata area)
            continue

        # Clean the header
        clean_header = re.sub(r"^#+\s*", "", header).strip("*# ")

        if _is_non_drill_header(clean_header):
            # Book structure header - attach body to current drill if exists,
            # otherwise skip
            if current_drill and body.strip():
                current_drill["body"] += "\n" + body
            continue

        if _is_subsection_header(clean_header):
            # This is a sub-section - attach to current drill
            if current_drill is not None:
                field = _classify_subsection(clean_header)
                existing = current_drill["subsections"].get(field, "")
                if existing:
                    current_drill["subsections"][field] = (
                        existing + "\n" + body
                    )
                else:
                    current_drill["subsections"][field] = body
            else:
                # Orphaned sub-section before any drill - create a drill from it
                logger.warning(
                    f"Orphaned sub-section '{clean_header}' before any drill"
                )
            continue

        # This is a new drill header
        if current_drill is not None:
            drills.append(current_drill)

        current_drill = {
            "name": clean_header,
            "body": body,
            "subsections": {},
        }

    # Don't forget the last drill
    if current_drill is not None:
        drills.append(current_drill)

    return drills


def _extract_metadata_field(
    text: str, pattern: str, max_length: int = 100
) -> str | None:
    """Extract a metadata field with strict matching.

    Only matches "Key: Value" on a single line, with value capped.
    """
    match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
    if not match:
        return None
    value = match.group(1).strip()
    # Cap length to avoid paragraph leakage
    if len(value) > max_length:
        # Truncate at first sentence or line break
        for sep in [". ", "\n", ",  "]:
            idx = value.find(sep)
            if 0 < idx <= max_length:
                value = value[:idx]
                break
        else:
            value = value[:max_length]
    return value if value else None


def _extract_drill_blocks(
    markdown: str,
    diagram_descriptions: dict[str, dict],
    images: dict[str, Path],
) -> list[DrillBlock]:
    """Parse drill blocks from markdown content with VLM enrichment."""
    sections = _split_into_header_sections(markdown)
    drill_groups = _group_drill_sections(sections)

    image_keys = list(images.keys())
    image_idx = 0
    drills: list[DrillBlock] = []

    for group in drill_groups:
        name = group["name"]
        if not name or len(name) < 3:
            continue

        # Skip drills with names that are clearly not drills
        if name.isdigit():
            continue

        # Build combined text for this drill
        all_text_parts = [group["body"]]
        for v in group["subsections"].values():
            all_text_parts.append(v)
        all_text = "\n".join(all_text_parts)

        # Skip very short groups with no substance
        if len(all_text.strip()) < 30 and not group["subsections"]:
            continue

        # Setup
        setup_text = group["subsections"].get("setup", "")
        if not setup_text and "setup" not in group["subsections"]:
            # Use the drill body as setup if no explicit setup section
            setup_text = group["body"]

        setup_desc = _extract_body_text(setup_text)
        equipment_text = group["subsections"].get("equipment", "")
        equipment = _extract_list_items(equipment_text) if equipment_text else []

        # Extract player count from setup text
        player_count = None
        pc_match = re.search(
            r"(\d+\s*(?:v|vs)\s*\d+[^.\n]*|"
            r"\d+\s+(?:field\s+)?players?[^.\n]*|"
            r"(?:goalkeeper|GK)\s+plus\s+\d+[^.\n]*)",
            setup_text,
            re.IGNORECASE,
        )
        if pc_match:
            player_count = pc_match.group(0).strip()

        # Area dimensions from setup
        area_dimensions = None
        area_match = re.search(
            r"(\d+\s*x\s*\d+\s*(?:meters?|yards?|m)[^.\n]*)",
            setup_text,
            re.IGNORECASE,
        )
        if area_match:
            area_dimensions = area_match.group(1).strip()

        # Sequence / Process
        seq_text = group["subsections"].get("sequence", "")
        sequence = _extract_list_items(seq_text) if seq_text else []

        # Rules
        rules_text = group["subsections"].get("rules", "")
        rules = _extract_list_items(rules_text) if rules_text else []

        # Scoring
        scoring_text = group["subsections"].get("scoring", "")
        scoring = _extract_list_items(scoring_text) if scoring_text else []

        # Coaching points
        cp_text = group["subsections"].get("coaching_points", "")
        coaching_points = _extract_list_items(cp_text) if cp_text else []

        # Progressions
        prog_text = group["subsections"].get("progressions", "")
        progressions = _extract_list_items(prog_text) if prog_text else []

        # Assign diagram - use next available image
        diagram = DiagramInfo()
        if image_idx < len(image_keys):
            key = image_keys[image_idx]
            desc = diagram_descriptions.get(key, {})
            is_diagram = desc.get("is_diagram", True)

            diagram = DiagramInfo(
                image_ref=str(images[key]),
                vlm_description=desc.get("description", ""),
                player_positions=_parse_player_positions(
                    desc.get("player_positions", [])
                ),
                movement_arrows=desc.get("movement_arrows"),
            )
            image_idx += 1

            # Skip ahead past non-diagram images to find the next real one
            # (but still assign the first image we encounter to this drill)
            while (
                image_idx < len(image_keys)
                and not diagram_descriptions.get(
                    image_keys[image_idx], {}
                ).get("is_diagram", True)
            ):
                image_idx += 1

        drill = DrillBlock(
            name=name,
            setup=DrillSetup(
                description=setup_desc,
                player_count=player_count,
                equipment=equipment,
                area_dimensions=area_dimensions,
            ),
            diagram=diagram,
            sequence=sequence,
            rules=rules,
            scoring=scoring,
            coaching_points=coaching_points,
            progressions=progressions,
        )
        drills.append(drill)

    return drills


async def extract_session_plan(
    document: DecomposedDocument,
    diagram_descriptions: dict[str, dict],
    source_filename: str,
) -> SessionPlan:
    """Extract a structured SessionPlan from decomposed document content.

    Args:
        document: Decomposed PDF content from Stage 1.
        diagram_descriptions: VLM analysis results from Stage 2.
        source_filename: Original PDF filename.

    Returns:
        SessionPlan model with extracted content.
    """
    logger.info(f"Extracting session plan from {source_filename}")
    markdown = document.markdown

    # --- Metadata extraction ---
    # Title: first # header, or fallback to filename
    title = ""
    title_match = re.search(r"^#\s+(.+?)$", markdown, re.MULTILINE)
    if title_match:
        title = title_match.group(1).strip()
    else:
        # Try first ## header as title
        h2_match = re.search(r"^##\s+(.+?)$", markdown, re.MULTILINE)
        if h2_match:
            title = h2_match.group(1).strip()
        else:
            title = (
                Path(source_filename)
                .stem.replace("_", " ")
                .replace("-", " ")
                .title()
            )

    # Try inline "Category: X Difficulty: Y" pattern first (common format)
    category = None
    difficulty = None
    inline_match = re.search(
        r"Category\s*:\s*(.+?)\s+Difficulty\s*:\s*(\w+)",
        markdown,
        re.IGNORECASE,
    )
    if inline_match:
        category = inline_match.group(1).strip()[:60]
        difficulty = inline_match.group(2).strip()

    # Fallback: separate lines
    if not category:
        category = _extract_metadata_field(
            markdown,
            r"^(?:Category|Topic|Theme)\s*:\s*(.+?)$",
            max_length=60,
        )
    if not difficulty:
        difficulty = _extract_metadata_field(
            markdown,
            r"^(?:Difficulty|Level)\s*:\s*(\w+)",
            max_length=30,
        )

    # Author: strict pattern, or look for AUTHORS section in book-format
    author = _extract_metadata_field(
        markdown,
        r"^(?:Author|Coach|Created\s+by)\s*:\s*(.+?)$",
        max_length=100,
    )
    if not author:
        # Book format: look for ## AUTHORS section
        authors_match = re.search(
            r"##\s+AUTHORS?\s*\n+(.+?)(?=\n##|\Z)",
            markdown,
            re.DOTALL | re.IGNORECASE,
        )
        if authors_match:
            # Extract just the first author name (bold or first sentence)
            author_text = authors_match.group(1).strip()
            # Look for bold names or names before comma
            name_match = re.search(
                r"\*\*(.+?)\*\*|^([A-Z][a-z]+\s+[A-Z][a-z]+)",
                author_text,
            )
            if name_match:
                author = (name_match.group(1) or name_match.group(2)).strip()
            else:
                # First sentence
                first_sentence = author_text.split(".")[0]
                if len(first_sentence) < 100:
                    author = first_sentence.strip()

    metadata = SessionMetadata(
        title=title,
        category=category,
        difficulty=difficulty,
        author=author,
    )

    drills = _extract_drill_blocks(
        markdown, diagram_descriptions, document.images
    )

    source = Source(
        filename=source_filename,
        page_count=document.page_count,
    )

    session_plan = SessionPlan(
        metadata=metadata,
        drills=drills,
        source=source,
    )

    logger.info(
        f"Extracted session plan: '{title}' with {len(drills)} drills"
    )
    return session_plan
