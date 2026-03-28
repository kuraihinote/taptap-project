# models.py — TapTap Analytics Chatbot (LLM Query Generation approach)

from typing import Any, Optional, Union
from pydantic import BaseModel, Field
from typing_extensions import TypedDict
from langchain_openai import AzureChatOpenAI
from constants import AZURE_GPT4O_MINI_CONFIG, LLM_TEMPERATURE, LLM_MAX_TOKENS


# ── Pydantic Models ───────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message:      str              = Field(..., description="Faculty's natural language question")
    college_name: Optional[str]    = Field(None, description="Faculty's college — scopes queries")
    history:      list[dict]       = []
    last_sql:        Optional[str] = None   # ← SQL from previous turn
    sql_chain_count: int           = 0      # ← how many times SQL has been modified in a row


class ChatResponse(BaseModel):
    answer:          str
    intent:          str
    data:            Optional[list[dict[str, Any]]] = None
    sql:             Optional[str]                  = None   # generated SQL (for debugging)
    sql_chain_count: int                            = 0      # returned so Streamlit can persist it
    error:           Optional[str]                  = None


# ── LangGraph State ───────────────────────────────────────────────────────────

class GraphState(TypedDict, total=False):
    message:      str
    college_name: Optional[str]
    history:      list[dict]
    last_sql:        Optional[str]   # ← SQL from previous turn
    sql_chain_count:  int              # ← how many times SQL has been modified in a row
    intent:       str
    data:         Optional[list[dict[str, Any]]]
    sql:          Optional[str]
    answer:       str
    error:        Optional[str]


# ── LLM ───────────────────────────────────────────────────────────────────────

gpt_4o_mini_llm = AzureChatOpenAI(
    openai_api_key=AZURE_GPT4O_MINI_CONFIG["api_key"],
    openai_api_version=AZURE_GPT4O_MINI_CONFIG["api_version"],
    azure_endpoint=AZURE_GPT4O_MINI_CONFIG["azure_endpoint"],
    deployment_name=AZURE_GPT4O_MINI_CONFIG["deployment_name"],
    temperature=LLM_TEMPERATURE,
    max_tokens=LLM_MAX_TOKENS,
)

if not gpt_4o_mini_llm:
    raise Exception("LLM initialisation failed.")