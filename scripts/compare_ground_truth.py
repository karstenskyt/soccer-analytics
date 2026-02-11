"""Compare ingested session plans against human-verified ground truth.

Usage:
    .venv\\Scripts\\python scripts/compare_ground_truth.py         # Windows
    .venv/bin/python scripts/compare_ground_truth.py              # Linux/macOS
"""

import json
import sys
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.fixtures.ground_truth import (
    NIELSEN_GROUND_TRUTH,
    ROBERTS_GROUND_TRUTH,
    WHEDDON_GROUND_TRUTH,
)

API_BASE = "http://localhost:8004"

GROUND_TRUTHS = {
    "Session Plan - Karsten Nielsen.pdf": NIELSEN_GROUND_TRUTH,
    "Session Plan - Ashley Roberts.pdf": ROBERTS_GROUND_TRUTH,
    "Session Plan - Phil Wheddon.pdf": WHEDDON_GROUND_TRUTH,
}


def fetch_latest_plans() -> dict[str, dict]:
    """Fetch all plans, keep only latest per source_filename."""
    req = Request(f"{API_BASE}/api/sessions")
    with urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
    sessions = data if isinstance(data, list) else data.get("sessions", [])

    # Keep latest by extraction_timestamp per source_filename
    latest: dict[str, dict] = {}
    for s in sessions:
        src = s.get("source_filename", "")
        ts = s.get("extraction_timestamp", "")
        if src not in latest or ts > latest[src]["extraction_timestamp"]:
            latest[src] = s
    return latest


def fetch_plan_detail(plan_id: str) -> dict:
    req = Request(f"{API_BASE}/api/sessions/{plan_id}")
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def compare_drill(idx: int, drill_data: dict, gt_drill: dict) -> list[str]:
    """Compare a single drill against ground truth. Returns list of findings."""
    findings = []
    drill_name = gt_drill.get("name", f"Drill {idx+1}")

    # Skip drills with no diagram
    if gt_drill.get("has_diagram") is False:
        findings.append(f"  [{drill_name}] No diagram expected -- skipping")
        return findings

    diagram = drill_data.get("diagram") or {}
    # Data may be directly on diagram or nested under enriched
    enriched = diagram.get("enriched") or diagram

    # Player count
    gt_players = gt_drill.get("players", {}).get("total", 0)
    positions = enriched.get("player_positions") or []
    vlm_players = len(positions)
    diff = abs(gt_players - vlm_players)
    status = "OK" if diff <= 1 else ("WARN" if diff <= 2 else "FAIL")
    findings.append(f"  [{drill_name}] Players: VLM={vlm_players}, GT={gt_players} [{status}]")

    # Player colors
    gt_detail = gt_drill.get("players", {}).get("detail", [])
    gt_colors = {}
    for d in gt_detail:
        c = d.get("color")
        if c:
            gt_colors[c] = gt_colors.get(c, 0) + d.get("count", 0)
    vlm_colors = {}
    for p in positions:
        c = p.get("color")
        if c:
            vlm_colors[c.lower()] = vlm_colors.get(c.lower(), 0) + 1
    colors_with = sum(1 for p in positions if p.get("color"))
    pct = (colors_with / vlm_players * 100) if vlm_players > 0 else 0
    findings.append(f"  [{drill_name}] Colors: {colors_with}/{vlm_players} have color ({pct:.0f}%)")
    if gt_colors:
        findings.append(f"    GT colors: {gt_colors}")
        findings.append(f"    VLM colors: {vlm_colors}")

    # Arrows
    gt_arrows = gt_drill.get("arrows", 0)
    vlm_arrows = len(enriched.get("arrows") or [])
    diff_a = abs(gt_arrows - vlm_arrows)
    status_a = "OK" if diff_a <= 1 else ("WARN" if diff_a <= 2 else "FAIL")
    findings.append(f"  [{drill_name}] Arrows: VLM={vlm_arrows}, GT={gt_arrows} [{status_a}]")

    # Goals
    gt_goals = gt_drill.get("goals", {})
    vlm_goals = enriched.get("goals") or []
    gt_goal_total = sum(gt_goals.values())
    vlm_goal_total = len(vlm_goals)
    status_g = "OK" if gt_goal_total == vlm_goal_total else "FAIL"
    findings.append(f"  [{drill_name}] Goals: VLM={vlm_goal_total}, GT={gt_goal_total} [{status_g}]")

    # Equipment
    gt_eq = gt_drill.get("equipment", {})
    vlm_eq = enriched.get("equipment") or []
    gt_eq_total = sum(v for k, v in gt_eq.items() if not k.endswith("_color"))
    vlm_eq_total = len(vlm_eq)
    status_e = "OK" if abs(gt_eq_total - vlm_eq_total) <= 1 else "FAIL"
    findings.append(f"  [{drill_name}] Equipment: VLM={vlm_eq_total}, GT={gt_eq_total} [{status_e}]")

    # Pitch view
    gt_pv = gt_drill.get("pitch_view")
    pv_data = enriched.get("pitch_view")
    if isinstance(pv_data, dict):
        vlm_pv = pv_data.get("view_type")
    else:
        vlm_pv = pv_data
    status_pv = "OK" if vlm_pv == gt_pv else ("CLOSE" if vlm_pv else "FAIL(null)")
    findings.append(f"  [{drill_name}] Pitch view: VLM={vlm_pv}, GT={gt_pv} [{status_pv}]")

    return findings


def main():
    try:
        latest = fetch_latest_plans()
    except URLError as e:
        print(f"ERROR: Cannot reach API at {API_BASE}: {e}", file=sys.stderr)
        sys.exit(1)

    print("=" * 70)
    print("GROUND TRUTH COMPARISON REPORT")
    print("=" * 70)

    total_checks = 0
    total_ok = 0
    total_fail = 0

    for src_file, gt in GROUND_TRUTHS.items():
        print(f"\n{'-' * 70}")
        print(f"  {src_file}")
        print(f"{'-' * 70}")

        if src_file not in latest:
            print(f"  NOT FOUND in database — was it ingested?")
            continue

        plan_id = latest[src_file]["id"]
        plan = fetch_plan_detail(plan_id)
        drills = plan.get("drills", [])

        # Drill count
        gt_count = gt["drill_count"]
        vlm_count = len(drills)
        print(f"  Drill count: VLM={vlm_count}, GT={gt_count} "
              f"[{'OK' if vlm_count == gt_count else 'MISMATCH'}]")
        print()

        # Compare each drill
        gt_drills = gt.get("drills", [])
        for i, gt_drill in enumerate(gt_drills):
            if i >= len(drills):
                print(f"  [Drill {i+1}] MISSING from extraction")
                total_fail += 1
                continue

            findings = compare_drill(i, drills[i], gt_drill)
            for f in findings:
                print(f)
                if "[OK]" in f or "[CLOSE]" in f:
                    total_ok += 1
                elif "[FAIL" in f or "[WARN" in f:
                    total_fail += 1
                total_checks += 1
            print()

    print(f"\n{'=' * 70}")
    print(f"SUMMARY: {total_ok} OK / {total_fail} issues / {total_checks} total checks")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
