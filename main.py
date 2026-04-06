# main.py — TapTap Analytics Chatbot

import decimal
from datetime import datetime, date
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage, AIMessage

from db import engine  # noqa: F401
from models import ChatRequest, ChatResponse
from llm import build_supervisor_graph
from constants import DUMMY_FACULTY_ID
from logger import logger


def _safe_convert(obj: Any) -> Any:
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

    # build_supervisor_graph is async — it sets up the checkpointer connection
    # and returns (graph, pg_ctx). pg_ctx is None when using MemorySaver.
    graph, pg_ctx = await build_supervisor_graph()

    app.state.graph  = graph
    app.state.pg_ctx = pg_ctx  # kept so we can close it cleanly on shutdown

    logger.info("Startup complete.")
    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    if pg_ctx is not None:
        logger.info("Closing Postgres checkpoint connection...")
        await pg_ctx.__aexit__(None, None, None)
    logger.info("Shutdown complete.")


app = FastAPI(
    title="TapTap Analytics Chatbot",
    version="3.0.0",
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
    return {"status": "ok", "version": "3.0.0"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    logger.info(f"/chat message='{request.message[:80]}' college='{request.college_name}'")

    # ── Thread ID ─────────────────────────────────────────────────────────────
    # LangGraph uses this as the key to load/save conversation history.
    # DUMMY_FACULTY_ID used for now.
    # In production: replace with the real faculty ID sent from the frontend.
    faculty_id = DUMMY_FACULTY_ID
    config = {"configurable": {"thread_id": faculty_id}}

    # ── Append college filter to current question if set ─────────────────────
    current_message = request.message
    if request.college_name:
        current_message += f" (filter to college: {request.college_name})"

    logger.info(f"/chat thread_id='{faculty_id}'")

    # ── Invoke graph ──────────────────────────────────────────────────────────
    # We no longer pass history from Streamlit — LangGraph loads the full
    # conversation history from the checkpointer using thread_id automatically.
    # Only the new HumanMessage needs to be passed each turn.
    try:
        result = await app.state.graph.ainvoke(
            {
                "messages":      [HumanMessage(content=current_message)],
                "user_query":    current_message,
                # Initialise turn-specific state fields each turn
                "direct_answer": None,
            },
            config=config,
        )
    except Exception as exc:
        logger.error(f"/chat graph error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))

    # ── Extract answer ────────────────────────────────────────────────────────
    answer: str = result.get("final_answer") or "No answer returned."

    # ── Extract data + SQL ────────────────────────────────────────────────────
    raw_data = result.get("sql_result") or []
    data     = _safe_convert(raw_data) if raw_data else None
    sql      = result.get("sql_query")
    error    = result.get("sql_error")

    # ── Extract intent ────────────────────────────────────────────────────────
    intent = result.get("domain") or ""
    if intent == "direct":
        intent = ""

    logger.info(f"/chat done | thread='{faculty_id}' | intent='{intent}' | rows={len(raw_data)} | error={error}")

    return ChatResponse(
        answer=answer,
        intent=intent,
        data=data,
        sql=sql,
        sql_chain_count=0,
        previous_intent=None,
        error=error,
    )