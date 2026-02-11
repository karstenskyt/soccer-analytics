"""Root conftest: ensure tests run inside the project .venv."""

import sys
from pathlib import Path

_VENV_DIR = Path(__file__).resolve().parent / ".venv"


def pytest_configure(config):
    """Abort early if the interpreter is not the project .venv Python."""
    exe = Path(sys.executable).resolve()
    if not str(exe).startswith(str(_VENV_DIR)):
        raise SystemExit(
            f"\n  Tests must run inside the project virtual environment.\n"
            f"  Active interpreter: {exe}\n"
            f"  Expected prefix:    {_VENV_DIR}\n\n"
            f"  Fix (Windows):  .venv\\Scripts\\python -m pytest tests/ -v\n"
            f"  Fix (Linux):    .venv/bin/python -m pytest tests/ -v\n"
        )
