# main.py — TapTap Analytics Chatbot (LLM Query Generation approach)

import decimal
from datetime import datetime, date
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from db import engine  # noqa: F401 — ensures DB connects at startup
from models import ChatRequest, ChatResponse, GraphState
from llm import build_graph
from logger import logger


def _safe_convert(obj: Any) -> Any:
    """Recursively convert non-JSON-serialisable types."""
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting TapTap Analytics Chatbot...")
    app.state.graph = build_graph()
    logger.info("Startup complete.")
    yield
    logger.info("Shutdown complete.")


app = FastAPI(
    title="TapTap Analytics Chatbot",
    version="2.0.0",
    description="LLM SQL generation chatbot for college faculty analytics.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    logger.info(f"/chat message='{request.message[:80]}' college='{request.college_name}'")

    initial_state: GraphState = {
        "message":      request.message,
        "college_name": request.college_name,
        "history":      request.history,
        "last_sql":        request.last_sql,        # ← thread last_sql into graph state
        "sql_chain_count": request.sql_chain_count, # ← track SQL modification chain
        "intent":       "unknown",
        "data":         None,
        "sql":          None,
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

    return ChatResponse(
        answer=final_state.get("answer") or "",
        intent=final_state.get("intent") or "unknown",
        data=clean_data,
        sql=final_state.get("sql"),
        sql_chain_count=final_state.get("sql_chain_count", 0),  # ← returned so Streamlit persists it
        error=final_state.get("error"),
    )