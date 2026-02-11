"""Stage 2: Diagram classification and multi-pass structured extraction.

Pass 1 (Classification): Lightweight check — is this a coaching diagram?
Pass 2a (Players): Focused player extraction with CV context.
Pass 2b (Arrows): Focused arrow extraction.
Pass 2c (Equipment+Goals): Focused equipment/goals extraction with CV context.
Pass 2d (Pitch View): Pitch view classification with CV context.
"""

from __future__ import annotations

import asyncio
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
    "server": "server",
    "srv": "server",
    "coach": "coach",
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
    temperature: float = 0.0,
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

    async with httpx.AsyncClient(timeout=600.0) as client:
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
                "server", "coach",
            ):
                role = None

        validated.append({
            "label": label,
            "x": x,
            "y": y,
            "role": role,
            "color": pos.get("color"),
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
# Pass 2a: Player extraction (with CV context)
# ---------------------------------------------------------------------------

PLAYER_SYSTEM_PROMPT = (
    "You are a soccer coaching diagram analyzer. Extract ONLY player positions. "
    "You MUST respond with a single valid JSON object and nothing else. "
    "No markdown, no explanation. Do NOT use <think> tags."
)

PLAYER_PROMPT_TEMPLATE = """{cv_context}

Using this as a starting point, identify all PLAYERS in the diagram.
For each player, provide: label (text near the player), x (0-100 left to right),
y (0-100 bottom/own goal to top/opponent goal), color, role.

Roles: GK="goalkeeper", A/A1="attacker", D/D1="defender", N/N1="neutral", S="server", C="coach"

IMPORTANT: Only count actual player markers (colored circles/icons with labels).
Do NOT count arrow endpoints, sequence numbers, or text labels as players.

Respond with: {{"players": [{{"label": "GK", "x": 50, "y": 10, "color": "green", "role": "goalkeeper"}}]}}
Use empty list [] if no players visible."""


# ---------------------------------------------------------------------------
# Pass 2b: Arrow extraction (standalone)
# ---------------------------------------------------------------------------

ARROW_SYSTEM_PROMPT = (
    "You are a soccer coaching diagram analyzer. Extract ONLY movement arrows. "
    "You MUST respond with a single valid JSON object and nothing else. "
    "No markdown, no explanation. Do NOT use <think> tags."
)

ARROW_PROMPT = """Extract all movement arrows from this soccer coaching diagram.
Coordinates: x 0-100 (left to right), y 0-100 (bottom/own goal to top/opponent goal).

Arrow types: "run" (solid line), "pass" (dashed), "shot" (thick/bold),
"dribble" (wavy), "cross", "through_ball", "movement" (generic)

For each arrow: start position, end position, type, associated player label if visible.

Respond with: {{"arrows": [{{"start_x": 30, "start_y": 55, "end_x": 45, "end_y": 75, "arrow_type": "run", "from_label": "A1", "sequence_number": 1}}]}}
Use empty list [] if no arrows visible."""


# ---------------------------------------------------------------------------
# Pass 2c: Equipment + Goals (with CV context)
# ---------------------------------------------------------------------------

EQUIPMENT_SYSTEM_PROMPT = (
    "You are a soccer coaching diagram analyzer. Extract ONLY equipment and goals. "
    "You MUST respond with a single valid JSON object and nothing else. "
    "No markdown, no explanation. Do NOT use <think> tags."
)

EQUIPMENT_PROMPT_TEMPLATE = """Computer vision detected {circle_count} colored circles in this diagram. Those are PLAYERS, not equipment.
Now identify all EQUIPMENT and GOALS separately.

Equipment types: "cone" (small triangle), "mannequin"/"dummy" (human-shaped figure),
"pole", "gate" (two cones with a line between), "hurdle", "mini_goal", "flag"
Goal types: "full_goal" (full-size goal with posts/net)

For each item: type, x (0-100), y (0-100), color if visible.
Goals MUST go in "goals", everything else in "equipment".

Respond with: {{"equipment": [{{"equipment_type": "mannequin", "x": 40, "y": 60, "color": "blue"}}], "goals": [{{"x": 50, "y": 100, "goal_type": "full_goal"}}]}}
Use empty lists [] if nothing visible."""


# ---------------------------------------------------------------------------
# Pass 2d: Pitch view classification (with CV context)
# ---------------------------------------------------------------------------

PITCH_VIEW_SYSTEM_PROMPT = (
    "You are a soccer pitch view classifier. "
    "You MUST respond with a single valid JSON object and nothing else. "
    "No markdown, no explanation. Do NOT use <think> tags."
)

PITCH_VIEW_PROMPT_TEMPLATE = """{cv_pitch_info}

Classify the portion of the soccer pitch shown in this diagram:
- "penalty_area" — shows only the area around one goal (18-yard box visible)
- "third" — shows approximately one third of the pitch (attacking/defending third)
- "half_pitch" — shows one half of the full pitch (center line visible)
- "full_pitch" — shows the entire pitch with both goals
- "custom" — non-standard or unclear

Respond with: {{"pitch_view": {{"view_type": "penalty_area"}}}}"""


# ---------------------------------------------------------------------------
# Multi-pass extraction functions
# ---------------------------------------------------------------------------


async def _extract_players(
    image_path: Path,
    cv_context: str,
    *,
    vlm: VLMBackend | None = None,
    ollama_url: str = "",
    model: str = "",
    max_tokens: int = 4096,
) -> list[dict]:
    """Pass 2a: Extract player positions with CV context."""
    prompt = PLAYER_PROMPT_TEMPLATE.format(cv_context=cv_context)

    content = await _vlm_call(
        image_path, ollama_url, model,
        system_prompt=PLAYER_SYSTEM_PROMPT,
        user_prompt=prompt,
        max_tokens=max_tokens,
        vlm=vlm,
        json_mode=True,
    )
    parsed = _extract_json_from_text(content)
    if parsed is None:
        # Retry with no-think suffix
        content = await _vlm_call(
            image_path, ollama_url, model,
            system_prompt=PLAYER_SYSTEM_PROMPT + _NO_THINK_SUFFIX,
            user_prompt=prompt,
            max_tokens=max_tokens,
            vlm=vlm,
            json_mode=True,
        )
        parsed = _extract_json_from_text(content)

    if parsed is None or not isinstance(parsed, dict):
        logger.warning(f"Pass 2a: Could not parse players for {image_path.name}")
        return []

    raw = parsed.get("players", [])
    return _validate_positions(raw) if isinstance(raw, list) else []


async def _extract_arrows(
    image_path: Path,
    *,
    vlm: VLMBackend | None = None,
    ollama_url: str = "",
    model: str = "",
    max_tokens: int = 4096,
) -> list[dict]:
    """Pass 2b: Extract movement arrows."""
    content = await _vlm_call(
        image_path, ollama_url, model,
        system_prompt=ARROW_SYSTEM_PROMPT,
        user_prompt=ARROW_PROMPT,
        max_tokens=max_tokens,
        vlm=vlm,
    )
    parsed = _extract_json_from_text(content)
    if parsed is None:
        content = await _vlm_call(
            image_path, ollama_url, model,
            system_prompt=ARROW_SYSTEM_PROMPT + _NO_THINK_SUFFIX,
            user_prompt=ARROW_PROMPT,
            max_tokens=max_tokens,
            vlm=vlm,
        )
        parsed = _extract_json_from_text(content)

    if parsed is None or not isinstance(parsed, dict):
        logger.warning(f"Pass 2b: Could not parse arrows for {image_path.name}")
        return []

    return parsed.get("arrows", []) if isinstance(parsed.get("arrows"), list) else []


async def _extract_equipment_goals(
    image_path: Path,
    circle_count: int,
    *,
    vlm: VLMBackend | None = None,
    ollama_url: str = "",
    model: str = "",
    max_tokens: int = 4096,
) -> dict:
    """Pass 2c: Extract equipment and goals."""
    prompt = EQUIPMENT_PROMPT_TEMPLATE.format(circle_count=circle_count)

    content = await _vlm_call(
        image_path, ollama_url, model,
        system_prompt=EQUIPMENT_SYSTEM_PROMPT,
        user_prompt=prompt,
        max_tokens=max_tokens,
        vlm=vlm,
    )
    parsed = _extract_json_from_text(content)
    if parsed is None:
        content = await _vlm_call(
            image_path, ollama_url, model,
            system_prompt=EQUIPMENT_SYSTEM_PROMPT + _NO_THINK_SUFFIX,
            user_prompt=prompt,
            max_tokens=max_tokens,
            vlm=vlm,
        )
        parsed = _extract_json_from_text(content)

    if parsed is None or not isinstance(parsed, dict):
        logger.warning(f"Pass 2c: Could not parse equipment for {image_path.name}")
        return {"equipment": [], "goals": []}

    return {
        "equipment": parsed.get("equipment", []),
        "goals": parsed.get("goals", []),
    }


async def _extract_pitch_view(
    image_path: Path,
    cv_pitch_info: str,
    *,
    vlm: VLMBackend | None = None,
    ollama_url: str = "",
    model: str = "",
    max_tokens: int = 1024,
) -> dict | None:
    """Pass 2d: Classify pitch view."""
    prompt = PITCH_VIEW_PROMPT_TEMPLATE.format(cv_pitch_info=cv_pitch_info)

    content = await _vlm_call(
        image_path, ollama_url, model,
        system_prompt=PITCH_VIEW_SYSTEM_PROMPT,
        user_prompt=prompt,
        max_tokens=max_tokens,
        vlm=vlm,
        json_mode=True,
    )
    parsed = _extract_json_from_text(content)
    if parsed is None:
        content = await _vlm_call(
            image_path, ollama_url, model,
            system_prompt=PITCH_VIEW_SYSTEM_PROMPT + _NO_THINK_SUFFIX,
            user_prompt=prompt,
            max_tokens=max_tokens,
            vlm=vlm,
            json_mode=True,
        )
        parsed = _extract_json_from_text(content)

    if parsed is None or not isinstance(parsed, dict):
        logger.warning(f"Pass 2d: Could not parse pitch view for {image_path.name}")
        return None

    return parsed.get("pitch_view")


async def extract_diagram_structures(
    images: dict[str, Path],
    classifications: dict[str, dict],
    ollama_url: str = "",
    model: str = "",
    max_tokens_pass2: int = 4096,
    *,
    vlm: VLMBackend | None = None,
) -> dict[str, dict]:
    """Run multi-pass extraction on all confirmed diagrams.

    For each diagram:
    1. CV preprocessing (sync, <100ms)
    2. 4 focused VLM passes in parallel (2a: players, 2b: arrows, 2c: equipment, 2d: pitch view)
    3. Merge results into unified dict

    Returns dict of image_key -> enriched structure data.
    """
    from .cv_preprocess import analyze_diagram, format_cv_context

    results: dict[str, dict] = {}
    diagram_count = 0

    for key, image_path in images.items():
        classification = classifications.get(key, {})
        if not classification.get("is_diagram", False):
            continue

        diagram_count += 1
        logger.info(f"Extracting structure from {key} (multi-pass + CV)")

        # Stage 1: CV preprocessing
        cv_analysis = analyze_diagram(image_path)
        logger.info(
            f"  CV detected {len(cv_analysis.circles)} circles: "
            f"{cv_analysis.circles_by_color}, view={cv_analysis.estimated_pitch_view}"
        )

        # Build CV context strings for VLM prompts
        cv_context = format_cv_context(cv_analysis)
        if cv_analysis.estimated_pitch_view:
            cv_pitch_info = (
                f"Pitch line analysis suggests this may be: "
                f"{cv_analysis.estimated_pitch_view}"
            )
        else:
            cv_pitch_info = (
                "No strong pitch line pattern detected by computer vision."
            )

        # Stage 2: 4 focused VLM passes in parallel
        players_task = _extract_players(
            image_path, cv_context,
            vlm=vlm, ollama_url=ollama_url, model=model,
            max_tokens=max_tokens_pass2,
        )
        arrows_task = _extract_arrows(
            image_path,
            vlm=vlm, ollama_url=ollama_url, model=model,
            max_tokens=max_tokens_pass2,
        )
        equipment_task = _extract_equipment_goals(
            image_path, len(cv_analysis.circles),
            vlm=vlm, ollama_url=ollama_url, model=model,
            max_tokens=max_tokens_pass2,
        )
        pitch_view_task = _extract_pitch_view(
            image_path, cv_pitch_info,
            vlm=vlm, ollama_url=ollama_url, model=model,
        )

        players, arrows, eq_goals, pitch_view = await asyncio.gather(
            players_task, arrows_task, equipment_task, pitch_view_task,
        )

        # Merge into unified structure dict
        data: dict = {
            "description": classification.get("description", ""),
            "player_positions": players,
            "arrows": arrows,
            "equipment": eq_goals.get("equipment", []),
            "goals": eq_goals.get("goals", []),
            "balls": [],
            "zones": [],
            "pitch_view": pitch_view,
            # Attach CV analysis for cross-validation
            "_cv_analysis": {
                "circles_by_color": cv_analysis.circles_by_color,
                "total_circles": len(cv_analysis.circles),
                "estimated_pitch_view": cv_analysis.estimated_pitch_view,
                "circles": [
                    {"x": c.x, "y": c.y, "color": c.color_name}
                    for c in cv_analysis.circles
                ],
            },
        }

        logger.info(
            f"  {key}: {len(players)} players, {len(arrows)} arrows, "
            f"{len(eq_goals.get('equipment', []))} equipment, "
            f"{len(eq_goals.get('goals', []))} goals, "
            f"view={pitch_view}"
        )

        results[key] = data

    logger.info(f"Multi-pass extraction complete: {diagram_count} diagrams")
    return results
