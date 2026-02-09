"""Stage 2: Diagram classification and structured extraction using VLM via Ollama API.

Pass 1 (Classification): Lightweight check — is this a coaching diagram?
Pass 2 (Full Structured Extraction): Comprehensive extraction of all diagram elements.
Pass 3 (Conditional Retry): Focused follow-up if Pass 2 yields sparse results.
"""

from __future__ import annotations

import base64
import json
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from .vlm_backend import VLMBackend

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

# ---------------------------------------------------------------------------
# Pass 1: Classification prompts (lightweight)
# ---------------------------------------------------------------------------

CLASSIFICATION_SYSTEM_PROMPT = (
    "You are a soccer coaching diagram classifier. You MUST respond with a "
    "single valid JSON object and nothing else. No markdown, no explanation, "
    "no text before or after the JSON. Do NOT use <think> tags."
)

CLASSIFICATION_PROMPT = """Classify this image. Is it a soccer/football coaching diagram?

If YES (tactical diagram with player markers, arrows, pitch lines):
{"is_diagram": true, "description": "Brief description of the drill shown"}

If NO (photo, logo, book cover, decorative graphic, text-only):
{"is_diagram": false, "description": "Brief description of what the image shows"}

Output ONLY the JSON object."""

# ---------------------------------------------------------------------------
# Pass 2: Full structured extraction prompt
# ---------------------------------------------------------------------------

EXTRACTION_SYSTEM_PROMPT = (
    "You are a soccer coaching diagram analyzer that extracts structured data. "
    "You MUST respond with a single valid JSON object and nothing else. "
    "No markdown, no explanation, no text before or after the JSON. "
    "Do NOT use <think> tags. Respond immediately with JSON."
)

EXTRACTION_PROMPT = """Extract elements from this soccer coaching diagram as JSON.
Coordinates: x 0-100 (left to right), y 0-100 (bottom/own goal to top/opponent goal).

Roles: A/A1="attacker", D/D1="defender", GK="goalkeeper", N/N1="neutral", S="server", C="coach"
Arrow types: "run", "pass", "shot", "dribble", "cross", "through_ball", "movement"
Equipment: "cone", "mannequin", "pole", "gate", "hurdle", "mini_goal", "full_goal", "flag"
Pitch views: "full_pitch", "half_pitch", "penalty_area", "third", "custom"

Format:
{"description": "...", "pitch_view": {"view_type": "half_pitch"}, "player_positions": [{"label": "A1", "x": 30, "y": 55, "role": "attacker"}], "arrows": [{"start_x": 30, "start_y": 55, "end_x": 45, "end_y": 75, "arrow_type": "run", "from_label": "A1", "sequence_number": 1}], "equipment": [{"equipment_type": "cone", "x": 25, "y": 45}], "goals": [{"x": 50, "y": 100, "goal_type": "full_goal"}], "balls": [{"x": 50, "y": 50}], "zones": []}

Use empty list [] for elements not visible. Output ONLY the JSON object."""

# ---------------------------------------------------------------------------
# Pass 3: Focused arrow/equipment retry prompt
# ---------------------------------------------------------------------------

ARROWS_EQUIPMENT_SYSTEM_PROMPT = (
    "You are a soccer coaching diagram detail extractor. You MUST respond with a "
    "single valid JSON object and nothing else. No markdown, no explanation. "
    "Do NOT use <think> tags. Respond immediately with JSON."
)

ARROWS_EQUIPMENT_PROMPT = """Look carefully at this soccer coaching diagram and extract ONLY the movement arrows and equipment.

Use the Opta coordinate system (x: 0-100, y: 0-100).

Arrow types: "run" (solid line), "pass" (dashed), "shot" (thick), "dribble" (wavy), "cross", "through_ball", "movement"
Equipment types: "cone", "mannequin", "pole", "gate", "hurdle", "mini_goal", "full_goal", "flag"

Respond with:
{"arrows": [{"start_x": 30, "start_y": 55, "end_x": 45, "end_y": 75, "arrow_type": "run", "from_label": "A1"}], "equipment": [{"equipment_type": "cone", "x": 25, "y": 45}], "goals": [{"x": 50, "y": 100, "goal_type": "full_goal"}], "balls": [{"x": 50, "y": 50}], "zones": []}

Output ONLY the JSON object."""


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------


def _extract_json_from_text(text: str) -> dict | None:
    """Extract a JSON object from text that may contain surrounding content.

    Tries multiple strategies:
    0. Strip <think>...</think> reasoning blocks (Qwen3-VL)
    1. Direct parse of the full text
    2. Strip markdown code fences
    3. Find the outermost { } pair
    """
    # Strategy 0: Strip <think> reasoning blocks that consume token budget
    # Handle both closed <think>...</think> and unclosed <think>... (token limit hit)
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # If an unclosed <think> remains, strip from <think> to end (or to first {)
    if "<think>" in cleaned:
        think_start = cleaned.index("<think>")
        # Check if there's JSON after the unclosed think block
        brace_pos = cleaned.find("{", think_start)
        if brace_pos != -1:
            cleaned = cleaned[:think_start] + cleaned[brace_pos:]
        else:
            cleaned = cleaned[:think_start]
    cleaned = cleaned.strip()

    # Strategy 1: Direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Strategy 2: Strip markdown fences
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
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


async def _vlm_call(
    image_path: Path,
    ollama_url: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 4096,
    temperature: float = 0.1,
    *,
    vlm: VLMBackend | None = None,
    json_mode: bool = False,
) -> str:
    """Send an image + prompt to the VLM and return the raw text content.

    If a VLMBackend is provided via the `vlm` kwarg, it is used directly.
    Otherwise, falls back to the legacy ollama_url/model HTTP call.

    Args:
        json_mode: If True, constrain output to valid JSON (Ollama format=json).
            Use for simple prompts only; complex prompts may return empty with this on.
    """
    if vlm is not None:
        resp = await vlm.chat_completion(
            image_path=image_path,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            json_mode=json_mode,
        )
        logger.debug(f"VLM raw response for {image_path.name}: {resp.content[:300]}")
        return resp.content

    # Legacy path: direct Ollama HTTP call (native /api/chat endpoint)
    image_bytes = image_path.read_bytes()
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    payload: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": user_prompt,
                "images": [image_b64],
            },
        ],
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
        "think": False,
        "stream": False,
    }
    if json_mode:
        payload["format"] = "json"

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{ollama_url}/api/chat",
            json=payload,
        )
        response.raise_for_status()
        result = response.json()

    content = result["message"]["content"]
    logger.debug(f"VLM raw response for {image_path.name}: {content[:300]}")
    return content


# Retry system prompt suffix that suppresses think-tag reasoning
_NO_THINK_SUFFIX = " Do NOT use <think> tags. Respond immediately with JSON."


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


# ---------------------------------------------------------------------------
# Pass 1: Classification
# ---------------------------------------------------------------------------


async def classify_single_diagram(
    image_path: Path,
    ollama_url: str = "",
    model: str = "",
    max_tokens: int = 1024,
    *,
    vlm: VLMBackend | None = None,
) -> dict:
    """Pass 1: Classify whether an image is a coaching diagram.

    Returns dict with 'is_diagram' bool and 'description' str.
    """
    content = await _vlm_call(
        image_path, ollama_url, model,
        system_prompt=CLASSIFICATION_SYSTEM_PROMPT,
        user_prompt=CLASSIFICATION_PROMPT,
        max_tokens=max_tokens,
        vlm=vlm,
        json_mode=True,
    )

    parsed = _extract_json_from_text(content)

    # Retry with thinking-suppressed prompt if first attempt fails
    if parsed is None:
        logger.info(f"Pass 1: Retrying {image_path.name} with no-think prompt")
        content = await _vlm_call(
            image_path, ollama_url, model,
            system_prompt=CLASSIFICATION_SYSTEM_PROMPT + _NO_THINK_SUFFIX,
            user_prompt=CLASSIFICATION_PROMPT,
            max_tokens=max_tokens,
            vlm=vlm,
            json_mode=True,
        )
        parsed = _extract_json_from_text(content)

    if parsed is not None:
        if "is_diagram" not in parsed:
            parsed["is_diagram"] = True
        return parsed

    logger.warning(f"Pass 1: Could not parse JSON for {image_path.name}, using fallback")
    lower = content.lower()
    is_photo = any(
        w in lower
        for w in ("photograph", "photo of", "portrait", "not a diagram", "book cover")
    )
    return {
        "is_diagram": not is_photo,
        "description": content[:200],
    }


async def classify_diagrams(
    images: dict[str, Path],
    ollama_url: str = "",
    model: str = "",
    max_tokens: int = 1024,
    *,
    vlm: VLMBackend | None = None,
) -> dict[str, dict]:
    """Pass 1: Classify all images as diagram or non-diagram.

    Returns dict of image_key -> classification result.
    """
    logger.info(f"Pass 1: Classifying {len(images)} images with {model}")
    results: dict[str, dict] = {}

    for key, image_path in images.items():
        logger.info(f"Pass 1: Classifying {key}")
        try:
            result = await classify_single_diagram(
                image_path, ollama_url, model, max_tokens=max_tokens, vlm=vlm,
            )
            is_diag = result.get("is_diagram", True)
            logger.info(
                f"  {key}: is_diagram={is_diag}, "
                f"desc={result.get('description', '')[:80]}..."
            )
            results[key] = result
        except Exception as e:
            logger.error(f"Pass 1: Failed for {key}: {e}")
            results[key] = {
                "is_diagram": False,
                "description": f"Classification failed: {e}",
            }

    diagram_count = sum(
        1 for d in results.values() if d.get("is_diagram", False)
    )
    logger.info(
        f"Pass 1 complete: {len(results)} classified, "
        f"{diagram_count} diagrams, {len(results) - diagram_count} non-diagrams"
    )
    return results


# ---------------------------------------------------------------------------
# Pass 2: Full Structured Extraction
# ---------------------------------------------------------------------------


async def extract_diagram_structure(
    image_path: Path,
    ollama_url: str = "",
    model: str = "",
    max_tokens: int = 8192,
    *,
    vlm: VLMBackend | None = None,
) -> dict:
    """Pass 2: Extract full structured data from a confirmed diagram.

    Returns dict with player_positions, arrows, equipment, goals, balls, zones, pitch_view.
    """
    try:
        content = await _vlm_call(
            image_path, ollama_url, model,
            system_prompt=EXTRACTION_SYSTEM_PROMPT,
            user_prompt=EXTRACTION_PROMPT,
            max_tokens=max_tokens,
            vlm=vlm,
        )
        parsed = _extract_json_from_text(content)

        # Retry with thinking-suppressed prompt if first attempt fails
        if parsed is None:
            logger.info(f"Pass 2: Retrying {image_path.name} with no-think prompt")
            content = await _vlm_call(
                image_path, ollama_url, model,
                system_prompt=EXTRACTION_SYSTEM_PROMPT + _NO_THINK_SUFFIX,
                user_prompt=EXTRACTION_PROMPT,
                max_tokens=max_tokens,
                vlm=vlm,
            )
            parsed = _extract_json_from_text(content)

        if parsed is None:
            logger.warning(
                f"Pass 2: Could not parse JSON for {image_path.name}. "
                f"Raw VLM output (first 500 chars): {content[:500]}"
            )
            return {}

        # Validate player positions
        raw_positions = parsed.get("player_positions", [])
        if isinstance(raw_positions, list):
            parsed["player_positions"] = _validate_positions(raw_positions)

        return parsed

    except Exception as e:
        logger.error(f"Pass 2: Failed for {image_path.name}: {e}")
        return {}


# ---------------------------------------------------------------------------
# Pass 3: Conditional arrow/equipment retry
# ---------------------------------------------------------------------------


async def extract_arrows_equipment(
    image_path: Path,
    ollama_url: str = "",
    model: str = "",
    max_tokens: int = 4096,
    *,
    vlm: VLMBackend | None = None,
) -> dict:
    """Pass 3: Focused extraction of arrows and equipment only.

    Used as a follow-up when Pass 2 found players but sparse arrows/equipment.
    """
    try:
        content = await _vlm_call(
            image_path, ollama_url, model,
            system_prompt=ARROWS_EQUIPMENT_SYSTEM_PROMPT,
            user_prompt=ARROWS_EQUIPMENT_PROMPT,
            max_tokens=max_tokens,
            vlm=vlm,
        )
        parsed = _extract_json_from_text(content)

        if parsed is None:
            logger.warning(f"Pass 3: Could not parse JSON for {image_path.name}")
            return {}

        return parsed

    except Exception as e:
        logger.error(f"Pass 3: Failed for {image_path.name}: {e}")
        return {}


def _is_sparse_result(data: dict) -> bool:
    """Check if Pass 2 result has players but sparse arrows/equipment."""
    has_players = len(data.get("player_positions", [])) > 0
    has_arrows = len(data.get("arrows", [])) > 0
    has_equipment = len(data.get("equipment", [])) > 0
    return has_players and not has_arrows and not has_equipment


async def extract_diagram_structures(
    images: dict[str, Path],
    classifications: dict[str, dict],
    ollama_url: str = "",
    model: str = "",
    max_tokens_pass2: int = 8192,
    max_tokens_pass3: int = 4096,
    *,
    vlm: VLMBackend | None = None,
) -> dict[str, dict]:
    """Run Pass 2 (+ conditional Pass 3) on all confirmed diagrams.

    Only processes images where is_diagram=True in classifications.
    Merges Pass 2 classification description into results.

    Returns dict of image_key -> enriched structure data.
    """
    results: dict[str, dict] = {}
    diagram_count = 0
    pass3_count = 0

    for key, image_path in images.items():
        classification = classifications.get(key, {})
        if not classification.get("is_diagram", False):
            continue

        diagram_count += 1
        logger.info(f"Pass 2: Extracting structure from {key}")

        data = await extract_diagram_structure(
            image_path, ollama_url, model, max_tokens=max_tokens_pass2, vlm=vlm,
        )

        # Carry forward the Pass 1 description if Pass 2 didn't provide one
        if not data.get("description") and classification.get("description"):
            data["description"] = classification["description"]

        # Pass 3: conditional retry for sparse results
        if _is_sparse_result(data):
            logger.info(f"Pass 3: Sparse result for {key}, retrying arrows/equipment")
            pass3_count += 1
            extra = await extract_arrows_equipment(
                image_path, ollama_url, model, max_tokens=max_tokens_pass3, vlm=vlm,
            )
            # Merge Pass 3 results into Pass 2 data
            for field in ("arrows", "equipment", "goals", "balls", "zones"):
                if extra.get(field) and not data.get(field):
                    data[field] = extra[field]

        positions_count = len(data.get("player_positions", []))
        arrows_count = len(data.get("arrows", []))
        equipment_count = len(data.get("equipment", []))
        logger.info(
            f"  {key}: {positions_count} players, {arrows_count} arrows, "
            f"{equipment_count} equipment items"
        )

        results[key] = data

    logger.info(
        f"Pass 2 complete: {diagram_count} diagrams processed, "
        f"{pass3_count} needed Pass 3 retry"
    )
    return results
