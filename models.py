# models.py — TapTap POD Analytics Chatbot
#
# Two sections:
#   1. SQLAlchemy ORM classes — map to actual DB tables (used in analytics.py)
#   2. Pydantic models        — define API request/response shapes (used in main.py)
#   3. LangGraph state        — TypedDict shared across the graph pipeline

from typing import Any, Optional
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Text, Boolean,
    DateTime, Date, Numeric, ForeignKey, ARRAY
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.dialects.postgresql import JSONB
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

Base = declarative_base()


# ══════════════════════════════════════════════════════════════════════════════
# 1. SQLAlchemy ORM — DB Table Mappings
# ══════════════════════════════════════════════════════════════════════════════

class User(Base):
    """public.user — stores all platform users including students and faculty."""
    __tablename__ = "user"
    __table_args__ = {"schema": "public"}

    id            = Column(String, primary_key=True)
    first_name    = Column(String)
    last_name     = Column(String)
    email         = Column(String)
    role          = Column(Text)
    college_id    = Column(Integer, ForeignKey("public.college.id"))
    department_id = Column(Integer)
    roll_number   = Column(String)

    college       = relationship("College", back_populates="users")


class College(Base):
    """public.college — college lookup table."""
    __tablename__ = "college"
    __table_args__ = {"schema": "public"}

    id   = Column(Integer, primary_key=True)
    name = Column(String)

    users = relationship("User", back_populates="college")


class PodSubmission(Base):
    """pod.pod_submission — every student's POD answer attempt."""
    __tablename__ = "pod_submission"
    __table_args__ = {"schema": "pod"}

    id                   = Column(Integer, primary_key=True)
    create_at            = Column(DateTime(timezone=True))
    update_at            = Column(DateTime(timezone=True))
    user_id              = Column(String, ForeignKey("public.user.id"))
    question_id          = Column(Integer)
    title                = Column(String)
    description          = Column(Text)
    language             = Column(String)
    domain_id            = Column(Integer)
    sub_domain_id        = Column(Integer)
    status               = Column(Text)          # 'pass' or 'fail'
    difficulty           = Column(Text)          # 'easy', 'medium', 'hard'
    points               = Column(Integer)
    obtained_score       = Column(Integer)
    pod_coins            = Column(Integer)
    badge_id             = Column(Integer)
    problem_of_the_day_id = Column(Integer, ForeignKey("pod.problem_of_the_day.id"))

    user                 = relationship("User")
    problem_of_the_day   = relationship("ProblemOfTheDay")


class PodAttempt(Base):
    """pod.pod_attempt — tracks if a student started a POD and how long they took."""
    __tablename__ = "pod_attempt"
    __table_args__ = {"schema": "pod"}

    id                   = Column(Integer, primary_key=True)
    create_at            = Column(DateTime(timezone=True))
    update_at            = Column(DateTime(timezone=True))
    user_id              = Column(String, ForeignKey("public.user.id"))
    problem_of_the_day_id = Column(Integer, ForeignKey("pod.problem_of_the_day.id"))
    status               = Column(Text)
    time_taken           = Column(Integer)       # seconds
    end_date             = Column(DateTime(timezone=True))
    pod_started_at       = Column(DateTime(timezone=True))

    user                 = relationship("User")
    problem_of_the_day   = relationship("ProblemOfTheDay")


class ProblemOfTheDay(Base):
    """pod.problem_of_the_day — the actual daily question metadata."""
    __tablename__ = "problem_of_the_day"
    __table_args__ = {"schema": "pod"}

    id                   = Column(Integer, primary_key=True)
    create_at            = Column(DateTime(timezone=True))
    update_at            = Column(DateTime(timezone=True))
    date                 = Column(Date)
    question_id          = Column(Integer)
    difficulty           = Column(Text)
    is_active            = Column(Boolean)
    unique_user_attempts = Column(Integer)
    cycle_number         = Column(Integer)
    position_in_cycle    = Column(Integer)
    type                 = Column(Text)


class PodStreak(Base):
    """pod.pod_streak — student consecutive day solving streaks."""
    __tablename__ = "pod_streak"
    __table_args__ = {"schema": "pod"}

    id                = Column(Integer, primary_key=True)
    create_at         = Column(DateTime(timezone=True))
    update_at         = Column(DateTime(timezone=True))
    user_id           = Column(String, ForeignKey("public.user.id"))
    start_date        = Column(DateTime(timezone=True))
    end_date          = Column(DateTime(timezone=True))
    type              = Column(Text)
    streak_count      = Column(Integer)
    is_active         = Column(Boolean)
    pod_submission_id = Column(Integer)

    user              = relationship("User")


class PodBadge(Base):
    """pod.pod_badge — badge definitions (name, type, criteria)."""
    __tablename__ = "pod_badge"
    __table_args__ = {"schema": "pod"}

    id               = Column(Integer, primary_key=True)
    name             = Column(String)
    description      = Column(String)
    badge_type       = Column(String)
    questions_count  = Column(Integer)
    streak_count     = Column(Integer)
    pod_category     = Column(Text)


class UserPodBadge(Base):
    """pod.user_pod_badge — which students have earned which badges."""
    __tablename__ = "user_pod_badge"
    __table_args__ = {"schema": "pod"}

    id           = Column(Integer, primary_key=True)
    create_at    = Column(DateTime(timezone=True))
    user_id      = Column(String, ForeignKey("public.user.id"))
    pod_badge_id = Column(Integer, ForeignKey("pod.pod_badge.id"))

    user         = relationship("User")
    badge        = relationship("PodBadge")


class UserCoins(Base):
    """pod.user_coins — coins earned by students from POD activity."""
    __tablename__ = "user_coins"
    __table_args__ = {"schema": "pod"}

    id                   = Column(Integer, primary_key=True)
    create_at            = Column(DateTime(timezone=True))
    user_id              = Column(String, ForeignKey("public.user.id"))
    coins_count          = Column(Integer)
    coin_earned_reason   = Column(Text)
    problem_of_the_day_id = Column(Integer)
    rewarded_date        = Column(Date)

    user                 = relationship("User")


class PodQuestionStatus(Base):
    """pod.pod_question_status — per-student question completion status."""
    __tablename__ = "pod_question_status"
    __table_args__ = {"schema": "pod"}

    user_id     = Column(String, ForeignKey("public.user.id"), primary_key=True)
    question_id = Column(Integer, primary_key=True)
    status      = Column(String)

    user        = relationship("User")


# ══════════════════════════════════════════════════════════════════════════════
# 2. Pydantic Models — API Request / Response shapes
# ══════════════════════════════════════════════════════════════════════════════

class ChatRequest(BaseModel):
    message: str = Field(..., description="Faculty's natural language question")
    college_name: Optional[str] = Field(
        None, description="Faculty's college — scopes all queries automatically"
    )


class ChatResponse(BaseModel):
    answer: str
    intent: str
    data: Optional[list[dict[str, Any]]] = None
    error: Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
# 3. LangGraph State — shared memory flowing through classify→execute→format
# ══════════════════════════════════════════════════════════════════════════════

class GraphState(TypedDict, total=False):
    message:      str
    college_name: Optional[str]
    intent:       str
    params:       dict[str, Any]
    data:         Optional[list[dict[str, Any]]]
    answer:       str
    error:        Optional[str]