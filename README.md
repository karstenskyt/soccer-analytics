# Soccer Analytics Service

A Docker-based service for extracting, understanding, and storing structured information from soccer coaching PDFs. Processes session plans and tactical manuals (such as Peters/Schumacher *Two Versus One*) through a 6-stage pipeline combining PDF decomposition, vision-language model analysis, structured data extraction, and visual semantic search via ColPali.

**[View Interactive Architecture Diagram](architecture.html)** (open locally in browser)

## Quick Start

### Prerequisites

- Docker Desktop with WSL2 (Windows) or Docker Engine (Linux)
- NVIDIA GPU with drivers installed (for VLM inference via Ollama)
- ~16 GB disk space for Docker images and model weights

### Windows (RTX 5070 Ti / CUDA)

```bash
cp .env.windows.example .env
docker compose -f docker-compose.yml -f docker-compose.windows.yml up -d
```

### DGX Spark (Blackwell / ARM64)

```bash
cp .env.dgx.example .env
docker compose -f docker-compose.yml -f docker-compose.dgx.yml up -d
```

### Verify

```bash
# Health check
curl http://localhost:8004/health

# Ingest a PDF
curl -X POST http://localhost:8004/api/ingest -F "file=@documents/Session Plan.pdf"

# List stored session plans
curl http://localhost:8004/api/sessions
```

## Architecture

Five Docker services compose the system. The orchestrator runs on CPU; Ollama and ColPali share the GPU with natural temporal separation (VLM inference completes before ColPali indexing).

```
PDF Upload ──> FastAPI Orchestrator (:8004)
                  │
                  ├─ Stage 1: Docling PDF Decomposition (CPU)
                  │     └─ Markdown text + extracted diagram images
                  │
                  ├─ Stage 2: VLM Diagram Analysis (Pass 1)
                  │     └─ Qwen3-VL via Ollama (:11434, GPU)
                  │
                  ├─ Stage 2b: Position Extraction (Pass 2)
                  │     └─ Focused VLM pass on confirmed diagrams
                  │
                  ├─ Stage 3: Schema Extraction
                  │     └─ Regex + header grouping → Pydantic models
                  │
                  ├─ Stage 4: Validation & Tactical Enrichment
                  │     └─ Game element, situation type, lane detection
                  │
                  ├─ Stage 5: PostgreSQL Storage (:5434)
                  │     └─ session_plans, drill_blocks, tactical_contexts
                  │
                  └─ Stage 6: ColPali Visual Indexing (best-effort)
                        └─ byaldi FAISS index via ColPali (:8005, GPU)

Search Query ──> GET /api/search?q=...
                  │
                  └─ Orchestrator → ColPali → FAISS similarity
                        └─ Results enriched with PostgreSQL metadata
```

| Service | Image | Port | GPU |
|---------|-------|------|-----|
| **Orchestrator** | `python:3.12-slim` + Docling | `8004` | No |
| **Ollama** | `ollama/ollama:latest` | `11434` | Yes (all layers) |
| **ColPali** | `python:3.12-slim` + byaldi | `8005` | Yes (ColQwen2) |
| **PostgreSQL** | `pgvector/pgvector:pg16` | `5434` | No |
| **Swagger UI** | `swaggerapi/swagger-ui` | `8084` | No |

ColQwen2 (~5-6 GB VRAM) + Qwen3-VL 8B (~5.4 GB) = ~11 GB total, fits in 16 GB RTX 5070 Ti. All ports are configurable via `.env`. See [Interactive Architecture Diagram](architecture.html) for a visual overview.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/ingest` | Upload and process a coaching PDF |
| `GET` | `/api/sessions` | List stored session plans |
| `GET` | `/api/sessions/{id}` | Get a session plan by ID |
| `PUT` | `/api/sessions/{id}` | Update a session plan |
| `GET` | `/api/sessions/{id}/drills` | List drills for a session plan |
| `GET` | `/api/sessions/{id}/drills/{idx}` | Get a specific drill by index |
| `GET` | `/api/sessions/{id}/drills/{idx}/diagram` | Render pitch diagram (PNG) |
| `POST` | `/api/render` | Render diagram from ad-hoc DrillBlock JSON |
| `GET` | `/api/search?q=...&k=5` | Semantic visual search across indexed drills |
| `GET` | `/health` | Health check |
| `GET` | `/docs` | Auto-generated OpenAPI docs |

### Ingest Example

```bash
curl -X POST http://localhost:8004/api/ingest \
  -F "file=@documents/my-session-plan.pdf"
```

Response:
```json
{
  "status": "success",
  "plan_id": "30102057-936e-4cd2-a938-7f4968b1e5c4",
  "indexed": true,
  "session_plan": {
    "metadata": {
      "title": "GK Training Session",
      "author": "Coach Smith",
      "category": "Goalkeeping: General",
      "difficulty": "Moderate"
    },
    "drills": [...],
    "source": {
      "filename": "my-session-plan.pdf",
      "page_count": 2
    }
  }
}
```

## MCP Server (Claude Code Integration)

An MCP server lets Claude Code query and analyze stored session plans directly.

### Setup

```bash
# Create a host-side virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS

# Install MCP dependencies (lightweight, no Docker needed)
pip install -r requirements.mcp.txt
```

The `.mcp.json` file in the project root registers the server with Claude Code automatically. Make sure Docker services are running so the MCP server can reach the API at `http://localhost:8004`.

### MCP Tools

| Tool | Description |
|------|-------------|
| `parse_session_plan` | List all session plans or get a specific plan by ID |
| `analyze_tactical_drill` | Get a drill with tactical context, optionally include diagram URL |
| `render_drill_diagram` | Render a pitch diagram and return base64-encoded image |
| `search_drills` | Semantic visual search across indexed drills (e.g. "counter attack 2v1") |

### Usage in Claude Code

Once configured, you can ask Claude Code:
- "Show me the stored session plans"
- "Analyze drill 0 from session plan {id}"
- "Render the pitch diagram for drill 1"
- "Search for pressing drills"

### Pitch Diagrams

Pitch diagrams are rendered using [mplsoccer](https://mplsoccer.readthedocs.io/) with opta-style coordinates (0–100). Player markers are color-coded by role:

| Role | Color |
|------|-------|
| Goalkeeper | Amber (`#F9A825`) |
| Attacker | Blue (`#1565C0`) |
| Defender | Red (`#C62828`) |

## Processing Pipeline

### Stage 1: PDF Decomposition

[Docling](https://github.com/DS4SD/docling) `DocumentConverter` extracts markdown text and diagram images from the PDF. OCR is enabled for scanned documents. Images are saved as PNG at 2x resolution.

### Stage 2: VLM Diagram Analysis (Two-Pass)

**Pass 1 — Classification & Description:** Each extracted image is sent to [Qwen3-VL](https://huggingface.co/Qwen/Qwen3-VL-8B) (8B) running on Ollama via the OpenAI-compatible vision API. The VLM classifies images as tactical diagrams or non-diagrams (photos, logos) and extracts movement patterns and tactical setup descriptions as structured JSON.

**Pass 2 — Position Extraction (Stage 2b):** A second, focused VLM pass runs only on confirmed diagrams (`is_diagram=true`) to extract player positions. The dedicated prompt uses Opta coordinates (0–100), few-shot examples, and label-to-role mapping (A→attacker, D→defender, GK→goalkeeper, N→neutral). Positions are validated (clamped to bounds, deduplicated, roles standardized) and merged into diagram descriptions before Stage 3. Configurable via `EXTRACT_POSITIONS` env var (default: `true`).

### Stage 3: Schema Extraction

Markdown content is parsed into structured drill blocks using header grouping. Sub-section headers (`Setup:`, `Sequence:`, `Coaching Points:`, `Variations:`, etc.) are grouped under their parent drill header. Book-structure headers (`AUTHORS`, `PART ONE`, `ACKNOWLEDGMENT`) are filtered out.

### Stage 4: Validation & Tactical Enrichment

Each drill block is analyzed for tactical context using keyword detection:

- **Game Elements**: Counter Attack, Pressing, Build-Up Play, Positional Attack, etc.
- **Situation Types**: Frontal, Lateral, Behind, Before (Peters/Schumacher 2v1 methodology)
- **Pitch Lanes**: Left Wing, Left Half-Space, Central Corridor, Right Half-Space, Right Wing
- **Numerical Advantage**: 2v1, 3v2, 4v3, etc.

### Stage 5: PostgreSQL Storage

Session plans, drill blocks, and tactical contexts are stored in PostgreSQL with pgvector support. Full JSON is preserved in JSONB columns for flexible querying.

### Stage 6: ColPali Visual Indexing (Best-Effort)

After database storage, the orchestrator sends the PDF to the ColPali service for visual indexing using [byaldi](https://github.com/AnswerDotAI/byaldi) (a RAG wrapper around [ColQwen2](https://huggingface.co/vidore/colqwen2-v1.0)). The ColPali service indexes each page into a FAISS index, enabling text-to-visual semantic search across all ingested PDFs. This stage is non-fatal — if the ColPali service is unavailable, ingestion still succeeds. Both services share the `upload_data` volume so no file transfer is needed.

## Data Model

### Peters/Schumacher 2v1 Methodology

The tactical enrichment system is built around the Peters/Schumacher framework from *Two Versus One*:

- **5 Lanes**: Left Wing, Left Half-Space, Central Corridor, Right Half-Space, Right Wing
- **4 Situation Types**: Frontal, Lateral, Behind, Before
- **9 Game Elements**: Counter Attack, Fast Break, Positional Attack, Pressing, Counter Pressing, Organized Defense, Build-Up Play, Transition to Attack, Transition to Defense

### Database Schema

```
session_plans
├── id (UUID, PK)
├── title, category, difficulty, author
├── source_filename, source_page_count
├── raw_json (JSONB - complete SessionPlan)
└── created_at, updated_at

drill_blocks
├── id (UUID, PK)
├── session_plan_id (FK → session_plans)
├── name, setup_description, player_count
├── sequence[], coaching_points[], progressions[]
├── vlm_description, image_ref
└── raw_json (JSONB - complete DrillBlock)

tactical_contexts
├── id (UUID, PK)
├── drill_block_id (FK → drill_blocks)
├── methodology, game_element
├── lanes[], situation_type
└── created_at
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_PORT` | `8004` | FastAPI orchestrator port |
| `OLLAMA_PORT` | `11434` | Ollama service port |
| `DB_PORT` | `5434` | PostgreSQL port |
| `DOCS_PORT` | `8084` | Swagger UI port |
| `COLPALI_PORT` | `8005` | ColPali visual retrieval service port |
| `VLM_MODEL` | `qwen3-vl:8b` | Ollama vision model |
| `COLPALI_MODEL` | `vidore/colqwen2-v1.0` | ColPali retrieval model |
| `POSTGRES_USER` | `soccer_analytics` | Database user |
| `POSTGRES_PASSWORD` | `changeme_soccer_2026` | Database password |
| `POSTGRES_DB` | `soccer_analytics` | Database name |
| `MAX_UPLOAD_SIZE_MB` | `50` | Max PDF upload size |
| `EXTRACT_POSITIONS` | `true` | Enable Pass 2 position extraction |
| `EXTRACTION_TIMEOUT_SECONDS` | `300` | Pipeline timeout |
| `COLPALI_TIMEOUT_SECONDS` | `120` | ColPali indexing/search timeout |

### Platform Profiles

The project uses multi-file Docker Compose composition:

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Base infrastructure (PostgreSQL, Swagger UI) |
| `docker-compose.windows.yml` | Windows/CUDA GPU services (Ollama + orchestrator) |
| `docker-compose.dgx.yml` | DGX ARM64/Blackwell GPU services |

| Aspect | Windows | DGX |
|--------|---------|-----|
| VLM Model | `qwen3-vl:8b` | `qwen3-vl:32b` |
| Orchestrator Base | `python:3.12-slim` | `nvcr.io/nvidia/pytorch:25.11-py3` |
| GPU | RTX 5070 Ti (16 GB) | Blackwell (128 GB) |

## Project Structure

```
soccer-analytics/
├── docker-compose.yml              # Base infrastructure
├── docker-compose.windows.yml      # Windows GPU services
├── docker-compose.dgx.yml          # DGX GPU services
├── Dockerfile.template             # Multi-platform orchestrator image
├── Dockerfile.colpali              # ColPali visual retrieval service
├── requirements.txt                # Common Python dependencies
├── requirements.windows.txt        # Windows-specific deps
├── requirements.dgx.txt            # DGX-specific deps
├── requirements.colpali.txt        # ColPali service deps (byaldi, torch)
├── requirements.mcp.txt            # Host-side MCP server deps
├── .mcp.json                       # MCP server registration
├── .env.windows.example            # Windows env template
├── .env.dgx.example                # DGX env template
├── architecture.html               # Interactive architecture diagram
├── scripts/
│   └── init-db.sql                 # Database schema
├── src/
│   ├── api/
│   │   ├── main.py                 # FastAPI app + lifespan
│   │   ├── config.py               # pydantic-settings config
│   │   ├── deps.py                 # DB session + Ollama/ColPali clients
│   │   └── routes/
│   │       ├── ingest.py           # POST /api/ingest (6-stage pipeline)
│   │       ├── sessions.py         # GET/PUT /api/sessions
│   │       ├── drills.py           # Drill + diagram endpoints
│   │       └── search.py           # GET /api/search (visual retrieval)
│   ├── colpali/
│   │   ├── __init__.py             # Package init
│   │   ├── config.py               # ColPali service settings
│   │   ├── index_manager.py        # byaldi FAISS index + doc mapping
│   │   └── app.py                  # Internal FastAPI (:8000 → :8005)
│   ├── mcp/
│   │   ├── __main__.py             # Entry point: python -m src.mcp
│   │   └── server.py               # MCP stdio server (4 tools)
│   ├── pipeline/
│   │   ├── decompose.py            # Stage 1: Docling PDF decomposition
│   │   ├── describe.py             # Stage 2 + 2b: VLM diagram analysis & position extraction
│   │   ├── extract.py              # Stage 3: Schema extraction
│   │   ├── validate.py             # Stage 4: Tactical enrichment
│   │   └── store.py                # Stage 5: PostgreSQL storage
│   ├── rendering/
│   │   └── pitch.py                # mplsoccer pitch diagram renderer
│   └── schemas/
│       ├── session_plan.py         # SessionPlan, DrillBlock models
│       └── tactical.py             # 2v1 methodology enums
├── tests/
│   ├── test_schemas.py
│   ├── test_pipeline.py
│   ├── test_rendering.py           # Pitch rendering unit tests
│   ├── test_mcp.py                 # MCP tool unit tests (mocked)
│   ├── test_colpali.py             # ColPali IndexManager unit tests
│   ├── test_search.py              # Search endpoint unit tests
│   └── test_api.py
└── documents/                      # Sample PDFs for testing
```

## Useful Commands

```bash
# Start services
docker compose -f docker-compose.yml -f docker-compose.windows.yml up -d

# View logs
docker compose -f docker-compose.yml -f docker-compose.windows.yml logs orchestrator -f

# Rebuild after code changes
docker compose -f docker-compose.yml -f docker-compose.windows.yml build orchestrator
docker compose -f docker-compose.yml -f docker-compose.windows.yml up -d orchestrator --force-recreate

# Check GPU usage
docker compose -f docker-compose.yml -f docker-compose.windows.yml logs ollama | grep "offloaded"

# Stop all services
docker compose -f docker-compose.yml -f docker-compose.windows.yml down

# Stop and remove volumes (clean slate)
docker compose -f docker-compose.yml -f docker-compose.windows.yml down -v
```

## Roadmap

- **Phase 1** (Complete): Foundation MVP - PDF ingestion, VLM analysis, PostgreSQL storage
- **Phase 1.5** (Complete): Extraction quality - drill grouping, metadata parsing, VLM classification
- **Phase 2** (Complete): MCP server interface, mplsoccer pitch diagram rendering
- **Phase 2.5** (Complete): Two-pass VLM position extraction for improved player position yield
- **Phase 3A** (Complete): ColPali/byaldi visual semantic search (text queries, FAISS index)
- **Phase 3B** (Planned): Image-upload search, session plan modification + PDF regeneration

## License

[MIT](LICENSE)
