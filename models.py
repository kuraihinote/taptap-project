# models.py — TapTap Analytics Chatbot (Supervisor Architecture)

from typing import Any, Optional
from pydantic import BaseModel, Field
from langchain_openai import AzureChatOpenAI
from constants import AZURE_GPT4O_MINI_CONFIG


# ── Pydantic Models ───────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message:      str              = Field(..., description="Faculty's natural language question")
    college_name: Optional[str]    = Field(None, description="Faculty's college — scopes queries")
    thread_id:    Optional[str]    = Field(None, description="Unique conversation ID from frontend")
    history:      list[dict]       = []
    last_sql:        Optional[str] = None   # ← SQL from previous turn
    sql_chain_count: int           = 0      # ← how many times SQL has been modified in a row
    previous_intent: Optional[str] = None   # ← intent from previous turn


class ChatResponse(BaseModel):
    answer:          str
    intent:          str
    data:            Optional[list[dict[str, Any]]] = None
    sql:             Optional[str]                  = None   # generated SQL (for debugging)
    sql_chain_count: int                            = 0      # returned so Streamlit can persist it
    previous_intent: Optional[str]                 = None   # ← returned so Streamlit can persist it
    error:           Optional[str]                  = None


# ── LLM ───────────────────────────────────────────────────────────────────────

gpt_4o_mini_llm = AzureChatOpenAI(
    openai_api_key=AZURE_GPT4O_MINI_CONFIG["api_key"],
    openai_api_version=AZURE_GPT4O_MINI_CONFIG["api_version"],
    azure_endpoint=AZURE_GPT4O_MINI_CONFIG["azure_endpoint"],
    deployment_name=AZURE_GPT4O_MINI_CONFIG["deployment_name"],
)

if not gpt_4o_mini_llm:
    raise Exception("LLM initialisation failed.")