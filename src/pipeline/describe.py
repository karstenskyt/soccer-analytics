"""Stage 2: Diagram description using Qwen3-VL via Ollama API."""

import base64
import json
import logging
import re
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

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
