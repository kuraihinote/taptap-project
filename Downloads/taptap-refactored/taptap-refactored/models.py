# models.py — TapTap POD Analytics Chatbot
#
# Three sections:
#   1. Pydantic models  — API request/response shapes (used in main.py)
#   2. LangGraph state  — TypedDict shared across classify→execute→format
#   3. LLM instantiation — gpt_4o_mini_llm imported by llm.py

from typing import Any, Optional, Union
from pydantic import BaseModel, Field
from typing_extensions import TypedDict
from langchain_openai import AzureChatOpenAI
from constants import AZURE_GPT4O_MINI_CONFIG, LLM_TEMPERATURE, LLM_MAX_TOKENS


# ══════════════════════════════════════════════════════════════════════════════
# 1. Pydantic Models — API Request / Response shapes
# ══════════════════════════════════════════════════════════════════════════════

class ChatRequest(BaseModel):
    message: str = Field(..., description="Faculty's natural language question")
    college_name: Optional[str] = Field(
        None, description="Faculty's college — scopes all queries automatically"
    )
    history: list[dict] = []


class ChatResponse(BaseModel):
    answer: str
    intent: str
    data: Optional[Union[list[dict[str, Any]], dict[str, Any]]] = None
    error: Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
# 2. LangGraph State — shared memory flowing through classify→execute→format
# ══════════════════════════════════════════════════════════════════════════════

class GraphState(TypedDict, total=False):
    message:      str
    college_name: Optional[str]
    history: list[dict]
    intent:       str
    params:       dict[str, Any]
    data:         Optional[Union[list[dict[str, Any]], dict[str, Any]]]
    answer:       str
    error:        Optional[str]


# ══════════════════════════════════════════════════════════════════════════════
# 3. LLM Instantiation — matches reference project pattern (models.py owns LLM)
# ══════════════════════════════════════════════════════════════════════════════

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