# main.py — TapTap Analytics Chatbot v3

import decimal
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from database import init_db_pool, close_db_pool
from models import ChatRequest, ChatResponse, GraphState
from supervisor import build_graph
from logger import logger


# ── JSON serialiser that handles Decimal, int64, etc. ─────────────────────────

def _safe_convert(obj: Any) -> Any:
    """Recursively convert non-JSON-serialisable types in a dict/list."""
    if isinstance(obj, list):
        return [_safe_convert(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _safe_convert(v) for k, v in obj.items()}
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    # asyncpg returns some ints as custom int subclasses — normalise them
    if hasattr(obj, '__int__') and not isinstance(obj, (bool, float, str)):
        try:
            return int(obj)
        except Exception:
            pass
    return obj


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting TapTap Analytics Chatbot v3…")
    await init_db_pool()
    app.state.graph = build_graph()
    logger.info("Startup complete.")
    yield
    logger.info("Shutting down…")
    await close_db_pool()
    logger.info("Shutdown complete.")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="TapTap Analytics Chatbot",
    version="3.0.0",
    description="LangGraph-powered analytics chatbot for college faculty.",
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
    return {"status": "ok", "version": "3.0.0"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    logger.info(f"/chat message='{request.message[:80]}' college='{request.college_name}'")

    graph = app.state.graph

    initial_state: GraphState = {
        "message": request.message,
        "college_name": request.college_name,
        "intent": "unknown",
        "params": {},
        "data": None,
        "answer": "",
        "error": None,
    }

    try:
        final_state: dict = await graph.ainvoke(initial_state)
    except Exception as exc:
        logger.error(f"/chat graph error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))

    # Sanitise data rows — convert Decimal, asyncpg int types, etc.
    raw_data = final_state.get("data")
    clean_data = _safe_convert(raw_data) if raw_data else None

    return ChatResponse(
        answer=final_state.get("answer") or "",
        intent=final_state.get("intent") or "unknown",
        data=clean_data,
        error=final_state.get("error"),
    )