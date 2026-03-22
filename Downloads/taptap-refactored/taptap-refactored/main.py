# main.py — TapTap POD Analytics Chatbot
# FastAPI application — entry point for the backend.
# Handles startup/shutdown, exposes /chat and /health endpoints.

import decimal
from datetime import datetime, date
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from db import engine  # noqa: F401 — importing engine ensures DB connects at startup
from models import ChatRequest, ChatResponse, GraphState
from llm import build_graph
from logger import logger


# ── Decimal / int64 serialiser ────────────────────────────────────────────────

def _safe_convert(obj: Any) -> Any:
    """Recursively convert non-JSON-serialisable types in dicts/lists."""
    if isinstance(obj, list):
        return [_safe_convert(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _safe_convert(v) for k, v in obj.items()}
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if hasattr(obj, "__int__") and not isinstance(obj, (bool, float, str)):
        try:
            return int(obj)
        except Exception:
            pass
    return obj


# ── Lifespan — runs at startup and shutdown ───────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting TapTap POD Analytics Chatbot...")
    app.state.graph = build_graph()   # compile LangGraph pipeline once
    logger.info("Startup complete.")
    yield
    logger.info("Shutdown complete.")


# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="TapTap POD Analytics Chatbot",
    version="1.0.0",
    description="LangGraph-powered POD analytics chatbot for college faculty.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    logger.info(f"/chat message='{request.message[:80]}' college='{request.college_name}'")

    initial_state: GraphState = {
        "message":      request.message,
        "college_name": request.college_name,
        "history":     request.history,
        "intent":       "unknown",
        "params":       {},
        "data":         None,
        "answer":       "",
        "error":        None,
    }

    try:
        final_state: dict = await app.state.graph.ainvoke(initial_state)
    except Exception as exc:
        logger.error(f"/chat graph error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))

    raw_data   = final_state.get("data")
    clean_data = _safe_convert(raw_data) if raw_data else None

    # Return query_type as the intent label so Streamlit chart routing
    # continues to work with the original fine-grained intent strings
    # (e.g. "pod_top_scorers") rather than the new broad domain strings.
    params     = final_state.get("params") or {}
    query_type = params.get("query_type") or final_state.get("intent") or "unknown"

    return ChatResponse(
        answer=final_state.get("answer") or "",
        intent=query_type,
        data=clean_data,
        error=final_state.get("error"),
    )