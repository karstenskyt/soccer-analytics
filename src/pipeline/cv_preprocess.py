"""CV preprocessing for coaching diagram images.

Detects colored circular markers (players), estimates pitch view from
line patterns, and returns structured analysis for VLM context injection.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class DetectedCircle:
    """A colored circular marker detected in the diagram."""

    x: float  # 0-100 normalized (left to right)
    y: float  # 0-100 normalized (top to bottom, raw image coords)
    color_name: str  # "red", "green", "blue", "yellow", "white", "black", "grey"
    color_hsv: tuple[int, int, int]  # H, S, V center value
    radius_px: int  # pixel radius


@dataclass
class CVAnalysis:
    """Computer vision analysis of a coaching diagram image."""

    circles: list[DetectedCircle] = field(default_factory=list)
    circles_by_color: dict[str, int] = field(default_factory=dict)
    has_pitch_lines: bool = False
    estimated_pitch_view: str | None = None
    image_width: int = 0
    image_height: int = 0
    dominant_background: str = "white"  # "green", "white", "grey"


# HSV ranges tuned for coaching diagrams
_COLOR_RANGES: dict[str, list[tuple[np.ndarray, np.ndarray]]] = {
    "red": [
        (np.array([0, 80, 80]), np.array([10, 255, 255])),  # low red
        (np.array([170, 80, 80]), np.array([180, 255, 255])),  # high red
    ],
    "green": [
        (np.array([35, 80, 80]), np.array([85, 255, 255])),
    ],
    "blue": [
        (np.array([100, 80, 80]), np.array([130, 255, 255])),
    ],
    "yellow": [
        (np.array([20, 80, 80]), np.array([35, 255, 255])),
    ],
    "grey": [
        (np.array([0, 0, 80]), np.array([180, 40, 180])),  # low sat, medium val
    ],
}

# Min/max contour area (in pixels at 1000px-wide scale) to count as a player marker
_MIN_CIRCLE_AREA = 100  # ~11px diameter
_MAX_CIRCLE_AREA = 5000  # ~80px diameter
_MIN_CIRCULARITY = 0.4  # How round the contour needs to be (1.0 = perfect)


def _detect_colored_circles(
    hsv_img: np.ndarray,
    color_name: str,
    ranges: list[tuple[np.ndarray, np.ndarray]],
    img_width: int,
    img_height: int,
) -> list[DetectedCircle]:
    """Detect circles of a specific color in an HSV image."""
    # Combine masks for multiple ranges (e.g., red wraps)
    mask = np.zeros(hsv_img.shape[:2], dtype=np.uint8)
    for lo, hi in ranges:
        mask |= cv2.inRange(hsv_img, lo, hi)

    # Morphological cleanup
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

    # Find contours
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    circles = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < _MIN_CIRCLE_AREA or area > _MAX_CIRCLE_AREA:
            continue

        # Circularity check
        perimeter = cv2.arcLength(cnt, True)
        if perimeter == 0:
            continue
        circularity = 4 * np.pi * area / (perimeter * perimeter)
        if circularity < _MIN_CIRCULARITY:
            continue

        # Get center and radius
        (cx, cy), radius = cv2.minEnclosingCircle(cnt)

        # Get average HSV inside the contour
        mask_single = np.zeros(hsv_img.shape[:2], dtype=np.uint8)
        cv2.drawContours(mask_single, [cnt], -1, 255, -1)
        mean_hsv = cv2.mean(hsv_img, mask=mask_single)[:3]

        circles.append(
            DetectedCircle(
                x=round(cx / img_width * 100, 1),
                y=round(cy / img_height * 100, 1),
                color_name=color_name,
                color_hsv=(int(mean_hsv[0]), int(mean_hsv[1]), int(mean_hsv[2])),
                radius_px=int(radius),
            )
        )

    return circles


def _dedup_circles(
    circles: list[DetectedCircle], threshold_pct: float = 1.5
) -> list[DetectedCircle]:
    """Remove duplicate circles within threshold_pct of each other (percentage of image)."""
    result: list[DetectedCircle] = []
    for c in circles:
        is_dup = False
        for existing in result:
            dist = ((c.x - existing.x) ** 2 + (c.y - existing.y) ** 2) ** 0.5
            if dist < threshold_pct:
                is_dup = True
                break
        if not is_dup:
            result.append(c)
    return result


def _detect_background(hsv: np.ndarray) -> str:
    """Detect dominant background color from corner samples."""
    h, w = hsv.shape[:2]
    # Sample 5 points: 4 corners + center
    points = [(10, 10), (10, w - 10), (h - 10, 10), (h - 10, w - 10), (h // 2, w // 2)]
    greens = 0
    for py, px in points:
        py = min(py, h - 1)
        px = min(px, w - 1)
        hue, sat, val = hsv[py, px]
        if 35 <= hue <= 85 and sat > 50:
            greens += 1
    if greens >= 3:
        return "green"
    # Check if mostly white/light
    avg_val = np.mean([hsv[min(py, h - 1), min(px, w - 1)][2] for py, px in points])
    return "white" if avg_val > 180 else "grey"


def _detect_pitch_view(img: np.ndarray) -> tuple[bool, str | None]:
    """Detect pitch lines and estimate view type using edge detection."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 180, threshold=50, minLineLength=50, maxLineGap=10
    )
    if lines is None or len(lines) < 3:
        return False, None

    # Analyze line patterns
    h, w = img.shape[:2]
    horizontal_lines = []
    vertical_lines = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        angle = abs(np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi)
        length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        if length < 30:
            continue
        if angle < 15 or angle > 165:
            horizontal_lines.append((x1, y1, x2, y2))
        elif 75 < angle < 105:
            vertical_lines.append((x1, y1, x2, y2))

    has_lines = len(horizontal_lines) + len(vertical_lines) > 3

    # Heuristic pitch view detection
    pitch_view = None
    if has_lines:
        # Check for midline (horizontal at ~40-60% of height)
        mid_lines = [
            line
            for line in horizontal_lines
            if 0.35 * h < (line[1] + line[3]) / 2 < 0.65 * h
            and abs(line[2] - line[0]) > 0.4 * w
        ]
        if mid_lines:
            pitch_view = "half_pitch"

        # Check for penalty box pattern (rectangle in upper portion)
        upper_h_lines = [
            line for line in horizontal_lines if (line[1] + line[3]) / 2 < 0.35 * h
        ]
        upper_v_lines = [
            line for line in vertical_lines if (line[1] + line[3]) / 2 < 0.35 * h
        ]
        if len(upper_h_lines) >= 2 and len(upper_v_lines) >= 2:
            pitch_view = "penalty_area"

    return has_lines, pitch_view


def analyze_diagram(image_path: Path) -> CVAnalysis:
    """Run CV preprocessing on a diagram image.

    Detects colored circular markers (players), estimates pitch view from
    line patterns, and returns structured analysis for VLM context injection.
    """
    img = cv2.imread(str(image_path))
    if img is None:
        logger.warning(f"Could not read image: {image_path}")
        return CVAnalysis()

    h, w = img.shape[:2]

    # Resize to consistent width for stable thresholds
    max_w = 1000
    if w > max_w:
        scale = max_w / w
        img = cv2.resize(img, (max_w, int(h * scale)))
        h, w = img.shape[:2]

    # Convert to HSV
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # Detect circles per color
    all_circles: list[DetectedCircle] = []
    for color_name, ranges in _COLOR_RANGES.items():
        circles = _detect_colored_circles(hsv, color_name, ranges, w, h)
        all_circles.extend(circles)

    # Deduplicate circles within 1.5% of each other (same marker, multiple colors)
    deduped = _dedup_circles(all_circles, threshold_pct=1.5)

    # Count by color
    by_color: dict[str, int] = {}
    for c in deduped:
        by_color[c.color_name] = by_color.get(c.color_name, 0) + 1

    # Background detection
    bg = _detect_background(hsv)

    # Pitch line detection
    has_lines, pitch_view = _detect_pitch_view(img)

    return CVAnalysis(
        circles=deduped,
        circles_by_color=by_color,
        has_pitch_lines=has_lines,
        estimated_pitch_view=pitch_view,
        image_width=w,
        image_height=h,
        dominant_background=bg,
    )


def format_cv_context(analysis: CVAnalysis) -> str:
    """Format CVAnalysis into a text string to inject into VLM prompts."""
    if not analysis.circles:
        return "Computer vision detected no colored circular markers in this diagram."

    parts = ["Computer vision detected these colored circles in the diagram:"]
    for color, count in sorted(analysis.circles_by_color.items()):
        positions = [(c.x, c.y) for c in analysis.circles if c.color_name == color]
        pos_str = ", ".join(f"({p[0]:.0f}, {p[1]:.0f})" for p in positions)
        parts.append(f"- {count} {color} circle(s) at approximately {pos_str}")

    parts.append(f"\nTotal: {len(analysis.circles)} colored markers detected.")

    if analysis.estimated_pitch_view:
        parts.append(f"Pitch line analysis suggests: {analysis.estimated_pitch_view}")

    return "\n".join(parts)
