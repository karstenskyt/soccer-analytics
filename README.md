# Soccer Analytics Service

A Docker-based service for extracting, understanding, and storing structured information from soccer coaching PDFs. Processes session plans and tactical manuals (such as Peters/Schumacher *Two Versus One*) through a 5-stage pipeline combining PDF decomposition, vision-language model analysis, and structured data extraction.

**[View Interactive Architecture Diagram](architecture.html)** (open locally in browser)

## Quick Start

### Prerequisites

- Docker Desktop with WSL2 (Windows) or Docker Engine (Linux)
- NVIDIA GPU with drivers installed (for VLM inference via Ollama)
- ~10 GB disk space for Docker images and model weights

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

Four Docker services compose the system. The orchestrator runs on CPU; only Ollama requires GPU access.

```
PDF Upload ──> FastAPI Orchestrator (:8004)
                  │
                  ├─ Stage 1: Docling PDF Decomposition (CPU)
                  │     └─ Markdown text + extracted diagram images
                  │
                  ├─ Stage 2: VLM Diagram Analysis
                  │     └─ Qwen3-VL via Ollama (:11434, GPU)
                  │
                  ├─ Stage 3: Schema Extraction
                  │     └─ Regex + header grouping → Pydantic models
                  │
                  ├─ Stage 4: Validation & Tactical Enrichment
                  │     └─ Game element, situation type, lane detection
                  │
                  └─ Stage 5: PostgreSQL Storage (:5434)
                        └─ session_plans, drill_blocks, tactical_contexts
```

| Service | Image | Port | GPU |
|---------|-------|------|-----|
| **Orchestrator** | `python:3.12-slim` + Docling | `8004` | No |
| **Ollama** | `ollama/ollama:latest` | `11434` | Yes (all layers) |
| **PostgreSQL** | `pgvector/pgvector:pg16` | `5434` | No |
| **Swagger UI** | `swaggerapi/swagger-ui` | `8084` | No |

All ports are configurable via `.env`. See [Interactive Architecture Diagram](architecture.html) for a visual overview.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/ingest` | Upload and process a coaching PDF |
| `GET` | `/api/sessions` | List stored session plans |
| `GET` | `/api/sessions/{id}` | Get a session plan by ID |
| `PUT` | `/api/sessions/{id}` | Update a session plan |
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

## Processing Pipeline

### Stage 1: PDF Decomposition

[Docling](https://github.com/DS4SD/docling) `DocumentConverter` extracts markdown text and diagram images from the PDF. OCR is enabled for scanned documents. Images are saved as PNG at 2x resolution.

### Stage 2: VLM Diagram Analysis

Each extracted image is sent to [Qwen3-VL](https://huggingface.co/Qwen/Qwen3-VL-8B) (8B) running on Ollama via the OpenAI-compatible vision API. The VLM classifies images as tactical diagrams or non-diagrams (photos, logos) and extracts player positions, movement patterns, and tactical setup descriptions as structured JSON.

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
| `VLM_MODEL` | `qwen3-vl:8b` | Ollama vision model |
| `POSTGRES_USER` | `soccer_analytics` | Database user |
| `POSTGRES_PASSWORD` | `changeme_soccer_2026` | Database password |
| `POSTGRES_DB` | `soccer_analytics` | Database name |
| `MAX_UPLOAD_SIZE_MB` | `50` | Max PDF upload size |
| `EXTRACTION_TIMEOUT_SECONDS` | `300` | Pipeline timeout |

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
├── requirements.txt                # Common Python dependencies
├── requirements.windows.txt        # Windows-specific deps
├── requirements.dgx.txt            # DGX-specific deps
├── .env.windows.example            # Windows env template
├── .env.dgx.example                # DGX env template
├── architecture.html               # Interactive architecture diagram
├── scripts/
│   └── init-db.sql                 # Database schema
├── src/
│   ├── api/
│   │   ├── main.py                 # FastAPI app + lifespan
│   │   ├── config.py               # pydantic-settings config
│   │   ├── deps.py                 # DB session + Ollama client
│   │   └── routes/
│   │       ├── ingest.py           # POST /api/ingest
│   │       └── sessions.py         # GET/PUT /api/sessions
│   ├── pipeline/
│   │   ├── decompose.py            # Stage 1: Docling PDF decomposition
│   │   ├── describe.py             # Stage 2: VLM diagram analysis
│   │   ├── extract.py              # Stage 3: Schema extraction
│   │   ├── validate.py             # Stage 4: Tactical enrichment
│   │   └── store.py                # Stage 5: PostgreSQL storage
│   └── schemas/
│       ├── session_plan.py         # SessionPlan, DrillBlock models
│       └── tactical.py             # 2v1 methodology enums
├── tests/
│   ├── test_schemas.py
│   ├── test_pipeline.py
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
- **Phase 2** (Planned): MCP server interface, mplsoccer diagram rendering
- **Phase 3** (Planned): DGX deployment, ColPali visual retrieval, session plan regeneration
