# main.py — TapTap POD Analytics Chatbot

import decimal
import datetime
import traceback
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from db import init_db, close_db
from models import ChatRequest, ChatResponse, GraphState
from llm import build_graph
from logger import logger


def _safe_convert(obj: Any) -> Any:
    if isinstance(obj, list):
        return [_safe_convert(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _safe_convert(v) for k, v in obj.items()}
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    if hasattr(obj, "__int__") and not isinstance(obj, (bool, float, str)):
        try:
            return int(obj)
        except Exception:
            pass
    return obj


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting TapTap POD Analytics Chatbot...")
    await init_db()
    app.state.graph = build_graph()
    logger.info("Startup complete.")
    yield
    logger.info("Shutting down...")
    await close_db()
    logger.info("Shutdown complete.")


app = FastAPI(
    title="TapTap POD Analytics Chatbot",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Global exception handler — catches EVERYTHING and prints to terminal ──────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print("\n" + "="*60, flush=True)
    print(f"GLOBAL ERROR on {request.method} {request.url}", flush=True)
    print(f"Exception type: {type(exc).__name__}", flush=True)
    print(f"Exception: {exc}", flush=True)
    traceback.print_exc()
    print("="*60 + "\n", flush=True)
    return JSONResponse(
        status_code=500,
        content={"detail": f"{type(exc).__name__}: {str(exc)}"}
    )


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    print(f"\n>>> /chat CALLED: message='{request.message[:60]}'", flush=True)
    logger.info(f"/chat message='{request.message[:80]}' college='{request.college_name}'")

    initial_state: GraphState = {
        "message":      request.message,
        "college_name": request.college_name,
        "intent":       "unknown",
        "params":       {},
        "data":         None,
        "answer":       "",
        "error":        None,
    }

    try:
        final_state: dict = await app.state.graph.ainvoke(initial_state)
    except Exception as exc:
        traceback.print_exc()
        logger.error(f"/chat graph error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))

    raw_data   = final_state.get("data")
    clean_data = _safe_convert(raw_data) if raw_data else None

    return ChatResponse(
        answer=final_state.get("answer") or "",
        intent=final_state.get("intent") or "unknown",
        data=clean_data,
        error=final_state.get("error"),
    )