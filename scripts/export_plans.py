"""Export all stored session plans as pretty-printed JSON files to the output/ folder.

Usage:
    .venv\\Scripts\\python scripts/export_plans.py         # Windows
    .venv/bin/python scripts/export_plans.py              # Linux/macOS
"""

import json
import re
import sys
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

API_BASE = "http://localhost:8004"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


def _safe_filename(source_filename: str) -> str:
    """Derive a clean output filename from source_filename."""
    stem = Path(source_filename).stem
    # Remove characters that are problematic in filenames
    clean = re.sub(r'[<>:"/\\|?*]', '', stem)
    return f"{clean}.json"


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Fetch session list
    try:
        req = Request(f"{API_BASE}/api/sessions")
        with urlopen(req, timeout=10) as resp:
            sessions = json.loads(resp.read())
    except URLError as e:
        print(f"ERROR: Cannot reach API at {API_BASE} — is Docker running?\n  {e}", file=sys.stderr)
        sys.exit(1)

    plans = sessions if isinstance(sessions, list) else sessions.get("sessions", sessions.get("plans", []))
    print(f"Found {len(plans)} session plans")

    for entry in plans:
        plan_id = entry.get("id") or entry.get("plan_id")
        source = entry.get("source_filename", plan_id)

        # Fetch full plan
        req = Request(f"{API_BASE}/api/sessions/{plan_id}")
        with urlopen(req, timeout=30) as resp:
            plan_data = json.loads(resp.read())

        filename = _safe_filename(source)
        out_path = OUTPUT_DIR / filename
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(plan_data, f, indent=2, ensure_ascii=False, default=str)

        n_drills = len(plan_data.get("drills", []))
        print(f"  Wrote {out_path.name} ({n_drills} drills)")

    print(f"\nDone — {len(plans)} files written to {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
