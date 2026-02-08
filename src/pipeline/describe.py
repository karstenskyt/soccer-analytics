"""Stage 2: Diagram description using Qwen3-VL via Ollama API."""

import base64
import json
import logging
import re
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# --- Role alias map for position standardization ---
_ROLE_ALIASES: dict[str, str] = {
    "gk": "goalkeeper",
    "goalie": "goalkeeper",
    "keeper": "goalkeeper",
    "forward": "attacker",
    "fwd": "attacker",
    "striker": "attacker",
    "att": "attacker",
    "back": "defender",
    "def": "defender",
    "cb": "defender",
    "fb": "defender",
    "mid": "midfielder",
    "mf": "midfielder",
    "neutral": "neutral",
}

# --- Pass 1 prompts (UNCHANGED) ---

# System message that enforces structured JSON output
VLM_SYSTEM_PROMPT = (
    "You are a soccer coaching diagram analyzer. You MUST respond with a "
    "single valid JSON object and nothing else. No markdown, no explanation, "
    "no text before or after the JSON. If the image is not a soccer/football "
    "coaching diagram (e.g. it is a photograph, logo, book cover, abstract "
    "graphic, or text-only image), respond with exactly: "
    '{"is_diagram": false, "description": "<brief description of what the image shows>"}'
)

DIAGRAM_ANALYSIS_PROMPT = """Analyze this image. If it is a soccer/football coaching diagram, respond with this JSON structure:

{"is_diagram": true, "description": "Overall description of the diagram", "player_positions": [{"label": "A1", "x": 30, "y": 60, "role": "attacker"}], "movement_arrows": "Description of movement patterns", "equipment": ["cones", "goals"], "tactical_setup": "e.g. 2v1 frontal attack drill"}

If it is NOT a coaching diagram (photo, logo, book cover, decorative graphic, text), respond:

{"is_diagram": false, "description": "Brief description of what the image shows"}

Remember: output ONLY the JSON object, no other text."""


def _extract_json_from_text(text: str) -> dict | None:
    """Extract a JSON object from text that may contain surrounding content.

    Tries multiple strategies:
    1. Direct parse of the full text
    2. Strip markdown code fences
    3. Find the outermost { } pair
    """
    cleaned = text.strip()

    # Strategy 1: Direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Strategy 2: Strip markdown fences
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Remove first line (```json or ```) and last ``` line
        inner_lines = []
        started = False
        for line in lines:
            if not started and line.startswith("```"):
                started = True
                continue
            if started and line.strip() == "```":
                break
            if started:
                inner_lines.append(line)
        if inner_lines:
            try:
                return json.loads("\n".join(inner_lines))
            except json.JSONDecodeError:
                pass

    # Strategy 3: Find outermost { } pair using brace counting
    first_brace = cleaned.find("{")
    if first_brace == -1:
        return None

    depth = 0
    in_string = False
    escape_next = False
    for i in range(first_brace, len(cleaned)):
        c = cleaned[i]
        if escape_next:
            escape_next = False
            continue
        if c == "\\":
            escape_next = True
            continue
        if c == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                candidate = cleaned[first_brace : i + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    # Try to fix common issues: trailing commas
                    fixed = re.sub(r",\s*}", "}", candidate)
                    fixed = re.sub(r",\s*]", "]", fixed)
                    try:
                        return json.loads(fixed)
                    except json.JSONDecodeError:
                        pass
                    break

    return None


async def describe_single_diagram(
    image_path: Path,
    ollama_url: str,
    model: str,
) -> dict:
    """Send a single diagram image to Qwen3-VL for analysis.

    Args:
        image_path: Path to the diagram image.
        ollama_url: Base URL of the Ollama service.
        model: VLM model name (e.g., 'qwen3-vl:8b').

    Returns:
        Dict with VLM analysis results including 'is_diagram' flag.
    """
    image_bytes = image_path.read_bytes()
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": VLM_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_b64}"
                        },
                    },
                    {
                        "type": "text",
                        "text": DIAGRAM_ANALYSIS_PROMPT,
                    },
                ],
            },
        ],
        "temperature": 0.1,
        "max_tokens": 1024,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{ollama_url}/v1/chat/completions",
            json=payload,
        )
        response.raise_for_status()
        result = response.json()

    content = result["choices"][0]["message"]["content"]

    parsed = _extract_json_from_text(content)
    if parsed is not None:
        # Ensure is_diagram field exists
        if "is_diagram" not in parsed:
            parsed["is_diagram"] = True
        return parsed

    logger.warning(f"Could not parse VLM JSON for {image_path.name}, using fallback")
    # Check if the raw text suggests it's not a diagram
    lower = content.lower()
    is_photo = any(
        w in lower
        for w in ("photograph", "photo of", "portrait", "not a diagram", "book cover")
    )
    return {
        "is_diagram": not is_photo,
        "description": content,
        "player_positions": [],
        "movement_arrows": "",
        "equipment": [],
        "tactical_setup": "",
    }


# --- Pass 2 prompts: Focused position extraction ---

POSITION_EXTRACTION_SYSTEM_PROMPT = (
    "You are a soccer coaching diagram position extractor. You MUST respond "
    "with a single valid JSON object and nothing else. No markdown, no "
    "explanation, no text before or after the JSON."
)

POSITION_EXTRACTION_PROMPT = """Look at this soccer coaching diagram and extract the positions of ALL player markers.

Use the Opta coordinate system:
- x: 0 (left) to 100 (right)
- y: 0 (bottom/own goal) to 100 (top/opponent goal)

Player markers include: circles, dots, filled/unfilled shapes, or labels like A1, D2, GK, N1.

Label-to-role mapping:
- A, A1, A2... = "attacker"
- D, D1, D2... = "defender"
- GK = "goalkeeper"
- N, N1... = "neutral"
- Numbered only (1, 2, 3) = use position context or null

Example 1 (2v1 drill):
{"player_positions": [{"label": "A1", "x": 30, "y": 60, "role": "attacker"}, {"label": "A2", "x": 50, "y": 55, "role": "attacker"}, {"label": "D1", "x": 40, "y": 70, "role": "defender"}]}

Example 2 (4v3 exercise):
{"player_positions": [{"label": "GK", "x": 50, "y": 5, "role": "goalkeeper"}, {"label": "A1", "x": 25, "y": 45, "role": "attacker"}, {"label": "A2", "x": 50, "y": 50, "role": "attacker"}, {"label": "A3", "x": 75, "y": 45, "role": "attacker"}, {"label": "A4", "x": 50, "y": 35, "role": "attacker"}, {"label": "D1", "x": 35, "y": 60, "role": "defender"}, {"label": "D2", "x": 50, "y": 65, "role": "defender"}, {"label": "D3", "x": 65, "y": 60, "role": "defender"}]}

If no player markers are visible, respond: {"player_positions": []}

Output ONLY the JSON object."""


def _validate_positions(raw_positions: list[dict]) -> list[dict]:
    """Validate and clean extracted player positions.

    - Clamp x, y to 0-100
    - Reject empty/whitespace labels
    - Standardize roles via alias map
    - Deduplicate by label (first occurrence wins)
    """
    seen_labels: set[str] = set()
    validated: list[dict] = []

    for pos in raw_positions:
        # Clamp coordinates
        try:
            x = max(0.0, min(100.0, float(pos.get("x", 50))))
            y = max(0.0, min(100.0, float(pos.get("y", 50))))
        except (ValueError, TypeError):
            continue

        # Validate label
        label = str(pos.get("label", "")).strip()
        if not label:
            continue

        # Deduplicate
        if label in seen_labels:
            continue
        seen_labels.add(label)

        # Standardize role
        role = pos.get("role")
        if role is not None:
            role = str(role).strip().lower()
            role = _ROLE_ALIASES.get(role, role)
            # Only keep known roles
            if role not in (
                "goalkeeper", "attacker", "defender", "midfielder", "neutral",
            ):
                role = None

        validated.append({
            "label": label,
            "x": x,
            "y": y,
            "role": role,
        })

    return validated


async def extract_positions_from_diagram(
    image_path: Path,
    ollama_url: str,
    model: str,
) -> list[dict]:
    """Send a diagram image to VLM for focused position extraction (Pass 2).

    Returns a list of validated position dicts, or [] on any failure.
    """
    try:
        image_bytes = image_path.read_bytes()
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": POSITION_EXTRACTION_SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_b64}"
                            },
                        },
                        {
                            "type": "text",
                            "text": POSITION_EXTRACTION_PROMPT,
                        },
                    ],
                },
            ],
            "temperature": 0.1,
            "max_tokens": 2048,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{ollama_url}/v1/chat/completions",
                json=payload,
            )
            response.raise_for_status()
            result = response.json()

        content = result["choices"][0]["message"]["content"]
        parsed = _extract_json_from_text(content)

        if parsed is None:
            logger.warning(
                f"Pass 2: Could not parse JSON for {image_path.name}"
            )
            return []

        raw_positions = parsed.get("player_positions", [])
        if not isinstance(raw_positions, list):
            logger.warning(
                f"Pass 2: player_positions is not a list for {image_path.name}"
            )
            return []

        validated = _validate_positions(raw_positions)
        logger.info(
            f"Pass 2: Extracted {len(validated)} positions from {image_path.name}"
        )
        return validated

    except Exception as e:
        logger.error(f"Pass 2: Failed for {image_path.name}: {e}")
        return []


async def extract_all_positions(
    images: dict[str, Path],
    diagram_descriptions: dict[str, dict],
    ollama_url: str,
    model: str,
) -> dict[str, list[dict]]:
    """Run focused position extraction on all confirmed diagrams.

    Only processes images where is_diagram=True in diagram_descriptions.

    Returns dict of image_key -> list of validated position dicts.
    """
    results: dict[str, list[dict]] = {}
    diagram_count = 0
    positions_found = 0

    for key, image_path in images.items():
        desc = diagram_descriptions.get(key, {})
        if not desc.get("is_diagram", False):
            continue

        diagram_count += 1
        logger.info(f"Pass 2: Extracting positions from {key}")
        positions = await extract_positions_from_diagram(
            image_path, ollama_url, model
        )
        if positions:
            results[key] = positions
            positions_found += len(positions)

    logger.info(
        f"Pass 2 complete: {diagram_count} diagrams processed, "
        f"{len(results)} yielded positions ({positions_found} total players)"
    )
    return results


async def describe_diagrams(
    images: dict[str, Path],
    ollama_url: str,
    model: str,
) -> dict[str, dict]:
    """Describe all diagram images using the VLM.

    Args:
        images: Dict of image_key -> file path.
        ollama_url: Base URL of the Ollama service.
        model: VLM model name.

    Returns:
        Dict of image_key -> VLM analysis results.
    """
    logger.info(f"Describing {len(images)} diagrams with {model}")
    descriptions: dict[str, dict] = {}

    for key, image_path in images.items():
        logger.info(f"Analyzing diagram: {key}")
        try:
            desc = await describe_single_diagram(
                image_path, ollama_url, model
            )
            is_diag = desc.get("is_diagram", True)
            logger.info(
                f"  {key}: is_diagram={is_diag}, "
                f"desc={desc.get('description', '')[:80]}..."
            )
            descriptions[key] = desc
        except Exception as e:
            logger.error(f"Failed to describe {key}: {e}")
            descriptions[key] = {
                "is_diagram": False,
                "description": f"Analysis failed: {e}",
                "player_positions": [],
                "movement_arrows": "",
                "equipment": [],
                "tactical_setup": "",
            }

    diagram_count = sum(
        1 for d in descriptions.values() if d.get("is_diagram", True)
    )
    logger.info(
        f"Diagram description complete: {len(descriptions)} analyzed, "
        f"{diagram_count} tactical diagrams, "
        f"{len(descriptions) - diagram_count} non-diagrams"
    )
    return descriptions
