# main.py — TapTap Analytics Chatbot

import decimal
import json
from datetime import datetime, date
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from db import engine  # noqa: F401
from models import ChatRequest, ChatResponse
from llm import build_supervisor_graph
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
    app.state.graph = build_supervisor_graph()
    logger.info("Startup complete.")
    yield
    logger.info("Shutdown complete.")


app = FastAPI(
    title="TapTap Analytics Chatbot",
    version="2.0.0",
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

    # Build message history for the supervisor
    # Include prior user questions + assistant answers for follow-up context
    messages = []
    for msg in (request.history or []):
        if msg.get("role") == "user":
            messages.append(HumanMessage(content=msg["content"]))
        elif msg.get("role") == "assistant":
            messages.append(AIMessage(content=msg["content"]))

    # Add college filter to current message if set
    current_message = request.message
    if request.college_name:
        current_message += f" (filter to college: {request.college_name})"

    messages.append(HumanMessage(content=current_message))

    try:
        result = await app.state.graph.ainvoke({"messages": messages})
    except Exception as exc:
        logger.error(f"/chat graph error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))

    all_messages = result.get("messages", [])

    # Extract the last AI message as the answer
    answer = ""
    for msg in reversed(all_messages):
        if isinstance(msg, AIMessage) and msg.content:
            answer = msg.content.strip()
            break

    if not answer:
        answer = "No answer returned."

    # Extract data and sql from tool messages
    data = None
    sql = None

    for msg in all_messages:
        if isinstance(msg, ToolMessage):
            try:
                tool_result = json.loads(msg.content)
                if isinstance(tool_result, dict) and "data" in tool_result:
                    data = _safe_convert(tool_result.get("data"))
                    sql  = tool_result.get("sql")
            except Exception as e:
                logger.warning(f"[main] ToolMessage parse failed: {e}")

    # Extract intent from AIMessage tool_calls
    intent = ""
    for msg in all_messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            tool_name = msg.tool_calls[0].get("name", "")
            intent = {
                "emp_data_tool":    "emp",
                "pod_data_tool":    "pod",
                "assess_data_tool": "assess",
            }.get(tool_name, "")


    return ChatResponse(
        answer=answer,
        intent=intent,
        data=data,
        sql=sql,
        sql_chain_count=0,
        previous_intent=None,
        error=None,
    )