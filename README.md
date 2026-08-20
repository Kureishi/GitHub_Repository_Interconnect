# GitHub Repository Interconnect

A full-stack application that ingests open-source GitHub repositories, statically analyses their exposed endpoints (REST APIs, CLIs, libraries, data files, schemas, ML models), classifies license compatibility for safe chaining, visualises module interconnections on an interactive canvas, and uses a local LLM (via LM Studio) to infer hidden endpoints and generate architecture reports.

---

## 🌟 Key Features

### 1. GitHub Repository Ingestion & Analysis
- Accepts any public GitHub repository URL or `owner/repo` identifier.
- Streams live analysis progress over **WebSockets** so you see results as they arrive.
- Detects endpoint categories via static heuristic analysis:
  - ⚡ **REST API** — FastAPI, Flask, Express, OpenAPI / Swagger definitions
  - ⌨️ **CLI Tool** — console entry points, `bin/` scripts, click / typer / argparse
  - 📦 **Library / Package** — pip (pyproject.toml / setup.py), npm, Cargo
  - 🗄️ **Data Files** — CSV, Parquet, HDF5, SQLite, Arrow
  - 🧩 **Data Structures** — Pydantic models, Protobuf, JSON Schema, TypedDict
  - 🐳 **Docker Container** — Dockerfile, docker-compose.yml
  - 🤖 **ML Model** — model weights, PyTorch, Hugging Face Transformers
  - ◈ **GraphQL & gRPC Services**

### 2. License Compatibility & Caution Banners
- Classifies SPDX licenses into **Permissive** (MIT, Apache-2.0, BSD-*), **Weak Copyleft** (LGPL, MPL-2.0), **Strong Copyleft** (GPL-*, AGPL-*), **Proprietary**, or **Unknown**.
- Shows caution banners on module cards for copyleft and proprietary licenses.
- Displays a per-connection license compatibility warning inside the **Connection Inspector** panel when incompatible modules are wired together.

### 3. Interactive Data-Flow Canvas
- Powered by **React Flow** with fully custom module node cards.
- **Left (purple) handles** = input endpoints (data consumer).
- **Right (green) handles** = output endpoints (data producer).
- Drag from any output handle to an input handle to create a directed data-flow edge.
- Click any edge to open the **Connection Inspector** slide-up panel showing the full endpoint pair and license compatibility status.
- Auto-layout, fit-to-view, and mini-map controls built in.

### 4. ✨ AI Features (LM Studio)
Powered by any OpenAI-compatible local model running in **LM Studio** (`http://localhost:1234`).

| Feature | How to trigger | What it does |
|---|---|---|
| **Endpoint Inference** | Click `✨ AI` on a module card | Streams AI-inferred endpoints from the repo README & file tree — useful when static analysis is incomplete |
| **Description Enrichment** | Available inside the AI Infer modal | Rewrites terse auto-detected descriptions into readable natural language |
| **Architecture Report** | Click `✨ AI Report` in the toolbar | Generates a 5-section Markdown report covering pipeline overview, data-flow analysis, endpoint contract mapping, license assessment, and optimisation recommendations |

The report modal supports:
- **📄 Open / Print PDF** — opens a clean printable window and triggers the print dialog (Save as PDF).
- **⬇️ .md** — downloads the raw Markdown file.
- **📋 Copy** — copies to clipboard.
- **🔄 Regenerate** — streams a fresh report.

### 5. Import & Export
- **Export** the full graph state (modules + connections) as a JSON file.
- **Import** a previously exported JSON file to restore a saved topology.
- GitHub PAT is stored in `localStorage` — never sent anywhere except the backend proxy.

---

## 🏗️ Architecture

```
GitHub Repository Interconnect
├── backend/                        # FastAPI application (Python ≥ 3.10)
│   ├── main.py                    # Server entry point, REST routes & WebSocket handlers
│   ├── models/
│   │   └── module.py              # Pydantic schemas: Module, Endpoint, Connection
│   ├── analyzer/
│   │   ├── github_client.py       # Async GitHub REST API client (PAT-aware)
│   │   ├── repo_analyzer.py       # Analysis orchestrator (WebSocket streaming generator)
│   │   ├── endpoint_extractor.py  # Heuristic static detectors for all endpoint types
│   │   └── license_checker.py     # SPDX license classifier & compatibility matrix
│   └── llm/
│       ├── lm_studio_client.py    # OpenAI-compatible async streaming client for LM Studio
│       ├── endpoint_inferrer.py   # AI endpoint inference from README + file tree
│       ├── enricher.py            # AI description enrichment for terse auto-detected endpoints
│       └── flow_reporter.py       # AI architecture & pipeline report generator
│
└── frontend/                       # React + Vite application (Node ≥ 18)
    ├── src/
    │   ├── App.jsx                # Root: React Flow canvas, toolbar, modal mounts
    │   ├── store/
    │   │   └── useModuleStore.js  # Zustand state: modules, connections, AI settings
    │   ├── api/
    │   │   └── client.js          # Axios HTTP client + WebSocket helpers
    │   ├── components/
    │   │   ├── ModuleNode.jsx      # Custom React Flow node card with endpoint handles
    │   │   ├── AddRepoPanel.jsx    # Sidebar: repo ingestion form + AI settings toggle
    │   │   ├── AISettingsPanel.jsx # LM Studio URL, model picker, connection tester
    │   │   ├── AIInferPanel.jsx    # Per-module AI inference & enrichment modal
    │   │   ├── FlowReportPanel.jsx # Full canvas AI architecture report modal
    │   │   ├── ConnectionPanel.jsx # Edge inspector slide-up panel
    │   │   ├── ModuleListPanel.jsx # Module list sidebar (collapsible)
    │   │   ├── EndpointBadge.jsx   # Endpoint type icon + label badge
    │   │   └── LicenseBadge.jsx    # License tier colour badge
    │   └── index.css              # Dark-mode design system (CSS custom properties)
    ├── index.html
    ├── vite.config.js             # API & WebSocket proxy → http://localhost:8000
    └── package.json
```

---

## 🚀 Quick Start

### Option A — pip install (end-user, no Node required)

The pre-built React frontend is bundled inside the Python wheel, so **only Python is needed at runtime**.

```bash
pip install repo-conn

# Optional: set a GitHub PAT to raise the API rate limit
export GITHUB_TOKEN=ghp_...

# Launch — starts the server and opens the browser automatically
repo-conn
```

Custom host/port:
```bash
repo-conn --port 9000
repo-conn --host 0.0.0.0 --port 8080   # expose on LAN
repo-conn --no-browser                  # skip auto-open
repo-conn --reload                      # enable hot-reload (dev)
```

The server runs at `http://127.0.0.1:8000`. Swagger docs at `/docs`.

---

### Option B — development (frontend hot-reload)

Use this if you are modifying the frontend source and want Vite's HMR.

#### Prerequisites
- **Python** ≥ 3.10
- **Node.js** ≥ 18 and npm
- *(Optional)* **LM Studio** running on `http://localhost:1234` for AI features

```bash
# 1. Clone
git clone https://github.com/<you>/github-repository-interconnect.git
cd github-repository-interconnect

# 2. Configure environment
cp .env.example .env
# Edit .env — add GITHUB_TOKEN and optionally LM_STUDIO_URL

# 3. Backend
pip install -e .
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

# 4. Frontend (separate terminal)
cd frontend
npm install
npm run dev       # http://localhost:5173
```

### *(Optional)* LM Studio setup

1. Download [LM Studio](https://lmstudio.ai/) and load any GGUF model (e.g. `google/gemma-3`, `mistral-7b-instruct`, `llama-3`).
2. Start the local server on port `1234` (default).
3. In the app sidebar, expand **✨ AI Settings**, enter `http://localhost:1234`, and click **Test**.
4. Select your loaded model from the dropdown.

---

## 🔌 Backend API Reference

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/state` | Returns persisted modules and connections |
| `DELETE` | `/api/modules/{id}` | Removes a module |
| `POST` | `/api/connections` | Creates a new endpoint connection |
| `DELETE` | `/api/connections/{id}` | Removes a connection |
| `POST` | `/api/export` | Returns full graph state as JSON |
| `POST` | `/api/import` | Loads graph state from uploaded JSON |
| `GET` | `/api/llm/health` | Tests LM Studio connectivity and lists available models |
| `POST` | `/api/llm/enrich/{module_id}` | Enriches module endpoint descriptions with AI |
| `WS` | `/ws/analyze` | Streams repo analysis events (progress, endpoints, done/error) |
| `WS` | `/ws/llm/infer/{module_id}` | Streams AI-inferred endpoints for a module |
| `WS` | `/ws/llm/report` | Streams full AI architecture report for current graph |

---

## 🧩 Multi-Repository Pipeline Examples

### REST API & Validation Pipeline
```
pallets/click  ──CLI Tool──►  pydantic/pydantic  ──Data Structures──►  fastapi/fastapi
 (CLI ingestion)               (schema validation)                       (REST API service)
```
All MIT/BSD — ✅ Freely chainable in open-source and commercial projects.

### ML Inference Pipeline
```
encode/httpx  ──HTTP Client──►  fastapi/fastapi  ──REST API──►  huggingface/transformers
(async HTTP)                    (inference server)              (tokenizer + model)
```

---

## ⚙️ Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GITHUB_TOKEN` | *(empty)* | GitHub PAT — raises rate limit from 60 to 5,000 req/hr |
| `HOST` | `127.0.0.1` | Uvicorn bind host |
| `PORT` | `8000` | Uvicorn bind port |

---

## 📄 License

MIT
