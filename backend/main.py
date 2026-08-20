"""
FastAPI application — GitHub Repository Interconnect backend.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .analyzer.repo_analyzer import analyze_repository
from .models.module import (
    AnalyzeRequest,
    AppState,
    Connection,
    Module,
    Endpoint,
    AnalysisStatus,
)
from .llm.lm_studio_client import LMStudioClient
from .llm.endpoint_inferrer import infer_endpoints
from .llm.enricher import enrich_module_endpoints
from .llm.flow_reporter import stream_flow_report

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="GitHub Repository Interconnect",
    description="Analyze GitHub repositories and visualize module interconnections.",
    version="1.1.0",
)

# CORS — allow the Vite dev server on port 5173
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# In-memory state (v1 — no persistence)
# ---------------------------------------------------------------------------

class StateStore:
    def __init__(self):
        self.modules: dict[str, Module] = {}
        self.connections: dict[str, Connection] = {}

    def get_state(self) -> AppState:
        return AppState(
            modules=list(self.modules.values()),
            connections=list(self.connections.values()),
        )


store = StateStore()


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/state", response_model=AppState)
async def get_state():
    """Return the current app state (all modules and connections)."""
    return store.get_state()


@app.post("/api/modules/{module_id}/position")
async def update_module_position(module_id: str, body: dict):
    """Update the canvas position of a module node."""
    if module_id not in store.modules:
        raise HTTPException(status_code=404, detail="Module not found")
    mod = store.modules[module_id]
    mod.position_x = float(body.get("x", mod.position_x))
    mod.position_y = float(body.get("y", mod.position_y))
    return {"ok": True}


@app.delete("/api/modules/{module_id}")
async def delete_module(module_id: str):
    """Remove a module and all its connections."""
    if module_id not in store.modules:
        raise HTTPException(status_code=404, detail="Module not found")
    del store.modules[module_id]
    # Remove associated connections
    to_delete = [
        cid for cid, c in store.connections.items()
        if c.source_module_id == module_id or c.target_module_id == module_id
    ]
    for cid in to_delete:
        del store.connections[cid]
    return {"ok": True}


@app.post("/api/connections", response_model=Connection)
async def create_connection(connection: Connection):
    """Record a connection between two module endpoints."""
    # Validate both modules exist
    for mid in (connection.source_module_id, connection.target_module_id):
        if mid not in store.modules:
            raise HTTPException(status_code=404, detail=f"Module {mid} not found")
    store.connections[connection.id] = connection
    return connection


@app.delete("/api/connections/{connection_id}")
async def delete_connection(connection_id: str):
    if connection_id not in store.connections:
        raise HTTPException(status_code=404, detail="Connection not found")
    del store.connections[connection_id]
    return {"ok": True}


@app.post("/api/export")
async def export_state():
    """Export the full state as JSON."""
    return store.get_state().model_dump()


@app.post("/api/import")
async def import_state(state: AppState):
    """Import a previously exported state."""
    store.modules = {m.id: m for m in state.modules}
    store.connections = {c.id: c for c in state.connections}
    return {"ok": True, "modules": len(store.modules), "connections": len(store.connections)}


# ---------------------------------------------------------------------------
# LLM routes
# ---------------------------------------------------------------------------

@app.get("/api/llm/health")
async def llm_health(lm_url: str = "http://localhost:1234"):
    """
    Check if LM Studio is reachable and return available models.
    Query param: lm_url (default: http://localhost:1234)
    """
    try:
        async with LMStudioClient(base_url=lm_url) as lm:
            result = await lm.health_check()
        return result
    except ConnectionError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail=str(e))


@app.post("/api/llm/enrich/{module_id}", response_model=Module)
async def enrich_module(
    module_id: str,
    body: dict,
):
    """
    Enrich a module's endpoint descriptions using LLM.
    Body: {"lm_url": "...", "model": "..." (optional)}
    """
    if module_id not in store.modules:
        raise HTTPException(status_code=404, detail="Module not found")
    mod = store.modules[module_id]
    lm_url = body.get("lm_url", "http://localhost:1234")
    model = body.get("model") or None
    try:
        enriched_eps = await enrich_module_endpoints(mod, lm_url=lm_url, model=model)
        mod = mod.model_copy(update={"endpoints": enriched_eps})
        store.modules[module_id] = mod
        return mod
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM error: {e}")


# ---------------------------------------------------------------------------
# WebSocket — streaming analysis
# ---------------------------------------------------------------------------

@app.websocket("/ws/analyze")
async def websocket_analyze(websocket: WebSocket):
    """
    WebSocket endpoint for streaming repository analysis.
    
    Client sends:  {"repo_url": "...", "github_token": "..."}
    Server sends:  AnalysisProgress JSON objects, one per step.
    Final message: status="done" with full module, or status="error".
    """
    await websocket.accept()
    try:
        raw = await websocket.receive_text()
        payload = json.loads(raw)
        repo_url: str = payload.get("repo_url", "").strip()
        github_token: Optional[str] = payload.get("github_token") or os.getenv("GITHUB_TOKEN")

        if not repo_url:
            await websocket.send_json({
                "status": "error",
                "message": "repo_url is required",
                "progress": 0,
                "error": "repo_url is required",
            })
            await websocket.close()
            return

        async for progress in analyze_repository(repo_url, github_token):
            data = progress.model_dump(mode="json")
            await websocket.send_json(data)

            if progress.status == AnalysisStatus.DONE and progress.module:
                # Save to store
                store.modules[progress.module.id] = progress.module

            if progress.status in (AnalysisStatus.DONE, AnalysisStatus.ERROR):
                break

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected during analysis")
    except Exception as e:
        logger.exception("WebSocket analysis error")
        try:
            await websocket.send_json({
                "status": "error",
                "message": str(e),
                "progress": 0,
                "error": str(e),
            })
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# WebSocket — AI endpoint inference (per module)
# ---------------------------------------------------------------------------

@app.websocket("/ws/llm/infer/{module_id}")
async def websocket_llm_infer(websocket: WebSocket, module_id: str):
    """
    Stream AI endpoint inference for a specific module.
    Client sends: {"lm_url": "...", "model": "...", "github_token": "..."}
    Server sends: {"type": "progress"|"token"|"done"|"error", ...}
    On "done": new AI endpoints are merged into the store and returned.
    """
    await websocket.accept()
    try:
        raw = await websocket.receive_text()
        payload = json.loads(raw)
        lm_url = payload.get("lm_url", "http://localhost:1234")
        model = payload.get("model") or None
        github_token = payload.get("github_token") or os.getenv("GITHUB_TOKEN")

        if module_id not in store.modules:
            await websocket.send_json({"type": "error", "message": "Module not found"})
            return

        mod = store.modules[module_id]

        async for event in infer_endpoints(
            mod,
            github_token=github_token,
            lm_url=lm_url,
            model=model,
        ):
            await websocket.send_json(event)

            # When done, merge the new endpoints into the store
            if event.get("type") == "done":
                new_ep_data = event.get("endpoints", [])
                new_eps = [Endpoint(**ep) for ep in new_ep_data]
                existing_names = {ep.name for ep in mod.endpoints}
                merged = list(mod.endpoints) + [
                    ep for ep in new_eps if ep.name not in existing_names
                ]
                mod = mod.model_copy(update={"endpoints": merged})
                store.modules[module_id] = mod
                # Send the updated module back
                await websocket.send_json({
                    "type": "module_updated",
                    "module": mod.model_dump(mode="json"),
                })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.exception("WS LLM infer error")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# WebSocket — AI flow report (full canvas)
# ---------------------------------------------------------------------------

@app.websocket("/ws/llm/report")
async def websocket_llm_report(websocket: WebSocket):
    """
    Stream a markdown pipeline report for the full module graph.
    Client sends: {"lm_url": "...", "model": "..."}
    Server sends: {"type": "token", "text": "..."} chunks then {"type": "done"}
    """
    await websocket.accept()
    try:
        raw = await websocket.receive_text()
        payload = json.loads(raw)
        lm_url = payload.get("lm_url", "http://localhost:1234")
        model = payload.get("model") or None

        modules = list(store.modules.values())
        connections = list(store.connections.values())

        async for token in stream_flow_report(
            modules=modules,
            connections=connections,
            lm_url=lm_url,
            model=model,
        ):
            await websocket.send_json({"type": "token", "text": token})

        await websocket.send_json({"type": "done"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.exception("WS LLM report error")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass

# ---------------------------------------------------------------------------
# Serve React build in production
# Resolves correctly both during local development (repo checkout) and
# when installed as a pip package (frontend/dist is included in the wheel).
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve().parent          # backend/
_FRONTEND_DIST = (_HERE.parent / "frontend" / "dist").resolve()

if _FRONTEND_DIST.is_dir():
    app.mount(
        "/assets",
        StaticFiles(directory=str(_FRONTEND_DIST / "assets")),
        name="assets",
    )

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str):
        """SPA fallback — serve index.html for all non-API routes."""
        # Do not intercept real API or WebSocket paths
        if full_path.startswith(("api/", "ws/", "docs", "openapi")):
            from fastapi import HTTPException
            raise HTTPException(status_code=404)
        return FileResponse(str(_FRONTEND_DIST / "index.html"))
