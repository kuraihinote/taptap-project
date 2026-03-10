# models.py — TapTap Analytics Chatbot v3

from typing import Any, Optional
from typing_extensions import TypedDict
from pydantic import BaseModel, Field


# ── Request / Response (Pydantic — used by FastAPI) ───────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., description="User's natural language query")
    college_name: Optional[str] = Field(
        None, description="Faculty's college context (injected server-side if available)"
    )


class ChatResponse(BaseModel):
    answer: str
    intent: str
    data: Optional[list[dict[str, Any]]] = None
    error: Optional[str] = None


# ── LLM structured output ─────────────────────────────────────────────────────

class ClassifiedIntent(BaseModel):
    intent: str = Field(..., description="One of the known intent labels or 'unknown'")
    params: dict[str, Any] = Field(default_factory=dict)


# ── Analytics result row shapes ───────────────────────────────────────────────

class StudentRow(BaseModel):
    reg_no: Optional[str] = None
    user_id: Optional[int] = None
    name: Optional[str] = None
    employability_score: Optional[float] = None
    employability_band: Optional[str] = None
    college_name: Optional[str] = None
    department: Optional[str] = None


class BandDistributionRow(BaseModel):
    employability_band: str
    count: int
    percentage: Optional[float] = None


class CollegeSummaryRow(BaseModel):
    college_name: str
    total_students: int
    avg_score: Optional[float] = None
    high_band_count: Optional[int] = None


class DepartmentSummaryRow(BaseModel):
    department: str
    total_students: int
    avg_score: Optional[float] = None


class HackathonRow(BaseModel):
    reg_no: Optional[str] = None
    name: Optional[str] = None
    hackathon_name: Optional[str] = None
    score: Optional[float] = None
    rank: Optional[int] = None


class PodRow(BaseModel):
    reg_no: Optional[str] = None
    name: Optional[str] = None
    pass_count: Optional[int] = None
    fail_count: Optional[int] = None
    total: Optional[int] = None


# ── LangGraph state ────────────────────────────────────────────────────────────
# FIX: Changed from Pydantic BaseModel → TypedDict.
#      LangGraph StateGraph requires TypedDict so node return dicts are merged
#      cleanly into state without needing model_dump() at every boundary.

class GraphState(TypedDict, total=False):
    message: str
    college_name: Optional[str]
    intent: str
    params: dict[str, Any]
    data: Optional[list[dict[str, Any]]]
    answer: str
    error: Optional[str]