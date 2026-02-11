# Soccer Analytics — Project Instructions

## Testing

Always run tests using the project virtual environment, never system Python:

```bash
# Windows
.venv\Scripts\python -m pytest tests/ -v

# Linux / macOS
.venv/bin/python -m pytest tests/ -v
```

A root `conftest.py` guard will abort with a clear error if the wrong
interpreter is used, but prefer getting it right in the first place.

## Virtual Environment

The project `.venv` contains all dependencies (FastAPI, mplsoccer, reportlab,
pytest, etc.). Install or update deps with:

```bash
.venv\Scripts\pip install -r requirements-dev.txt   # Windows
```

## Code Style

- Pydantic models live in `src/schemas/`
- Pipeline stages live in `src/pipeline/`
- Rendering lives in `src/rendering/`
- All new Optional fields on Pydantic models must default to `None`
- Coordinates use the 0-100 normalized (Opta) system
- Enum values are lowercase strings
