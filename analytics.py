# analytics.py — TapTap POD Analytics Chatbot
# All POD queries using SQLAlchemy ORM.
# No raw SQL strings — queries are built using SQLAlchemy's query API.
# All student name/college info comes from public.user + public.college joins.

from datetime import date, timedelta, timezone, datetime as dt_datetime
from typing import Optional

from sqlalchemy import func, case, distinct, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_session
from models import (
    User, College, PodSubmission, PodAttempt,
    ProblemOfTheDay, PodStreak, PodBadge,
    UserPodBadge, UserCoins,
)
from logger import logger


def _today_utc() -> date:
    """Return today's date in UTC to match DB timestamps stored as UTC."""
    return dt_datetime.now(timezone.utc).date()


def _student_display_name(user: User) -> str:
    """Helper to combine first_name + last_name."""
    return f"{user.first_name or ''} {user.last_name or ''}".strip()


def _rows_to_dicts(rows) -> list[dict]:
    """Convert SQLAlchemy Row objects to plain dicts."""
    return [dict(r._mapping) for r in rows]


# ── Daily Activity ────────────────────────────────────────────────────────────

async def get_who_solved_today(college_name: Optional[str] = None) -> list[dict]:
    """Students who passed the POD today."""
    logger.debug(f"get_who_solved_today college={college_name}")
    today = _today_utc()
    async with get_session() as session:
        q = (
            select(
                User.id,
                (User.first_name + " " + User.last_name).label("name"),
                User.email,
                College.name.label("college"),
                PodSubmission.title,
                PodSubmission.difficulty,
                PodSubmission.language,
                PodSubmission.obtained_score,
                PodSubmission.create_at,
            )
            .join(PodSubmission, PodSubmission.user_id == User.id)
            .join(College, College.id == User.college_id)
            .where(
                PodSubmission.status == "pass",
                func.date(PodSubmission.create_at) == today,
            )
        )
        if college_name:
            q = q.where(College.name.ilike(f"%{college_name}%"))
        q = q.order_by(PodSubmission.create_at.desc())
        result = await session.execute(q)
        return _rows_to_dicts(result.all())


async def get_attempt_count_today(college_name: Optional[str] = None) -> list[dict]:
    """Total number of students who attempted the POD today."""
    logger.debug(f"get_attempt_count_today college={college_name}")
    today = _today_utc()
    async with get_session() as session:
        q = (
            select(
                func.count(distinct(PodAttempt.user_id)).label("total_attempts"),
                func.count(distinct(
                    case((PodSubmission.status == "pass", PodSubmission.user_id))
                )).label("passed"),
                func.count(distinct(
                    case((PodSubmission.status == "fail", PodSubmission.user_id))
                )).label("failed_only"),
            )
            .join(User, User.id == PodAttempt.user_id)
            .join(College, College.id == User.college_id)
            .outerjoin(
                PodSubmission,
                and_(
                    PodSubmission.user_id == PodAttempt.user_id,
                    PodSubmission.problem_of_the_day_id == PodAttempt.problem_of_the_day_id,
                )
            )
            .where(func.date(PodAttempt.create_at) == today)
        )
        if college_name:
            q = q.where(College.name.ilike(f"%{college_name}%"))
        result = await session.execute(q)
        return _rows_to_dicts(result.all())


async def get_question_today() -> list[dict]:
    """What is today's POD question."""
    logger.debug("get_question_today")
    async with get_session() as session:
        # Use is_active=True — avoids timezone mismatch (DB date is UTC, server may be IST)
        q = (
            select(
                ProblemOfTheDay.id,
                ProblemOfTheDay.date,
                ProblemOfTheDay.difficulty,
                ProblemOfTheDay.type,
                ProblemOfTheDay.unique_user_attempts,
                ProblemOfTheDay.is_active,
            )
            .where(ProblemOfTheDay.is_active == True)
            .order_by(ProblemOfTheDay.date.desc())
            .limit(1)
        )
        result = await session.execute(q)
        return _rows_to_dicts(result.all())


async def get_fastest_solvers(
    college_name: Optional[str] = None,
    limit: int = 10,
) -> list[dict]:
    """Students who solved today's POD in the fastest time."""
    logger.debug(f"get_fastest_solvers college={college_name} limit={limit}")
    today = _today_utc()
    async with get_session() as session:
        # Join with pod_submission to confirm they actually passed
        # pod_attempt.status = "completed" means they finished, not necessarily passed
        q = (
            select(
                (User.first_name + " " + User.last_name).label("name"),
                College.name.label("college"),
                PodAttempt.time_taken,
                PodAttempt.pod_started_at,
                PodAttempt.end_date,
            )
            .join(User, User.id == PodAttempt.user_id)
            .join(College, College.id == User.college_id)
            .join(
                PodSubmission,
                and_(
                    PodSubmission.user_id == PodAttempt.user_id,
                    PodSubmission.problem_of_the_day_id == PodAttempt.problem_of_the_day_id,
                    PodSubmission.status == "pass",
                )
            )
            .where(
                func.date(PodAttempt.create_at) == today,
                PodAttempt.status == "completed",
                PodAttempt.time_taken.isnot(None),
            )
        )
        if college_name:
            q = q.where(College.name.ilike(f"%{college_name}%"))
        q = q.order_by(PodAttempt.time_taken.asc()).limit(limit)
        result = await session.execute(q)
        return _rows_to_dicts(result.all())


async def get_not_attempted_today(
    college_name: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """Students who have NOT attempted today's POD."""
    logger.debug(f"get_not_attempted_today college={college_name}")
    today = _today_utc()
    async with get_session() as session:
        # Subquery — users who DID attempt today
        attempted_subq = (
            select(PodAttempt.user_id)
            .where(func.date(PodAttempt.create_at) == today)
            .scalar_subquery()
        )
        q = (
            select(
                (User.first_name + " " + User.last_name).label("name"),
                User.email,
                College.name.label("college"),
            )
            .join(College, College.id == User.college_id)
            .where(
                User.role == "Student",
                User.id.not_in(attempted_subq),
            )
        )
        if college_name:
            q = q.where(College.name.ilike(f"%{college_name}%"))
        q = q.order_by(User.first_name).limit(limit)
        result = await session.execute(q)
        return _rows_to_dicts(result.all())


# ── Pass / Fail Performance ───────────────────────────────────────────────────

async def get_pass_fail_summary(
    college_name: Optional[str] = None,
    date_filter: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """Pass/fail count per student. date_filter: 'today' or 'YYYY-MM-DD'."""
    logger.debug(f"get_pass_fail_summary college={college_name} date={date_filter}")

    async with get_session() as session:
        q = (
            select(
                (User.first_name + " " + User.last_name).label("name"),
                College.name.label("college"),
                func.count(distinct(
                    case((PodSubmission.status == "pass", PodSubmission.question_id))
                )).label("pass_count"),
                func.count(distinct(
                    case((PodSubmission.status == "fail", PodSubmission.question_id))
                )).label("fail_count"),
                func.count(distinct(PodSubmission.question_id)).label("total_questions"),
            )
            .join(PodSubmission, PodSubmission.user_id == User.id)
            .join(College, College.id == User.college_id)
            .where(User.role == "Student")
        )
        if college_name:
            q = q.where(College.name.ilike(f"%{college_name}%"))
        if date_filter == "today":
            q = q.where(func.date(PodSubmission.create_at) == _today_utc())
        elif date_filter:
            q = q.where(func.date(PodSubmission.create_at) == date_filter)

        q = (
            q.group_by(User.id, User.first_name, User.last_name, College.name)
            .order_by(func.count(distinct(
                case((PodSubmission.status == "pass", PodSubmission.question_id))
            )).desc())
            .limit(limit)
        )
        result = await session.execute(q)
        return _rows_to_dicts(result.all())


async def get_pass_rate(college_name: Optional[str] = None) -> list[dict]:
    """Overall pass rate for a college."""
    logger.debug(f"get_pass_rate college={college_name}")
    async with get_session() as session:
        q = (
            select(
                College.name.label("college"),
                func.count(distinct(
                    case((PodSubmission.status == "pass", PodSubmission.id))
                )).label("total_passes"),
                func.count(distinct(PodSubmission.id)).label("total_submissions"),
                (
                    func.round(
                        func.count(distinct(case((PodSubmission.status == "pass", PodSubmission.id))))
                        * 100.0
                        / func.nullif(func.count(distinct(PodSubmission.id)), 0),
                        2
                    )
                ).label("pass_rate_percent"),
            )
            .join(User, User.id == PodSubmission.user_id)
            .join(College, College.id == User.college_id)
            .where(User.role == "Student")
        )
        if college_name:
            q = q.where(College.name.ilike(f"%{college_name}%"))
        q = q.group_by(College.name).order_by(College.name)
        result = await session.execute(q)
        return _rows_to_dicts(result.all())


async def get_top_passers(
    college_name: Optional[str] = None,
    limit: int = 10,
) -> list[dict]:
    """Students with the highest number of unique questions passed."""
    logger.debug(f"get_top_passers college={college_name} limit={limit}")
    async with get_session() as session:
        q = (
            select(
                (User.first_name + " " + User.last_name).label("name"),
                College.name.label("college"),
                func.count(distinct(PodSubmission.question_id)).label("questions_passed"),
                func.sum(PodSubmission.obtained_score).label("total_score"),
            )
            .join(PodSubmission, PodSubmission.user_id == User.id)
            .join(College, College.id == User.college_id)
            .where(
                PodSubmission.status == "pass",
                User.role == "Student",
            )
        )
        if college_name:
            q = q.where(College.name.ilike(f"%{college_name}%"))
        q = (
            q.group_by(User.id, User.first_name, User.last_name, College.name)
            .order_by(func.count(distinct(PodSubmission.question_id)).desc())
            .limit(limit)
        )
        result = await session.execute(q)
        return _rows_to_dicts(result.all())


async def get_never_passed(
    college_name: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """Students who have never passed a POD."""
    logger.debug(f"get_never_passed college={college_name}")
    async with get_session() as session:
        passed_subq = (
            select(PodSubmission.user_id)
            .where(PodSubmission.status == "pass")
            .scalar_subquery()
        )
        attempted_subq = (
            select(PodSubmission.user_id)
            .scalar_subquery()
        )
        q = (
            select(
                (User.first_name + " " + User.last_name).label("name"),
                User.email,
                College.name.label("college"),
            )
            .join(College, College.id == User.college_id)
            .where(
                User.role == "Student",
                User.id.in_(attempted_subq),
                User.id.not_in(passed_subq),
            )
        )
        if college_name:
            q = q.where(College.name.ilike(f"%{college_name}%"))
        q = q.order_by(User.first_name).limit(limit)
        result = await session.execute(q)
        return _rows_to_dicts(result.all())


async def get_weekly_passers(
    college_name: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """Students who passed at least one POD this week."""
    logger.debug(f"get_weekly_passers college={college_name}")
    week_start = _today_utc() - timedelta(days=_today_utc().weekday())
    async with get_session() as session:
        q = (
            select(
                (User.first_name + " " + User.last_name).label("name"),
                College.name.label("college"),
                func.count(distinct(PodSubmission.question_id)).label("questions_passed_this_week"),
            )
            .join(PodSubmission, PodSubmission.user_id == User.id)
            .join(College, College.id == User.college_id)
            .where(
                PodSubmission.status == "pass",
                func.date(PodSubmission.create_at) >= week_start,
                User.role == "Student",
            )
        )
        if college_name:
            q = q.where(College.name.ilike(f"%{college_name}%"))
        q = (
            q.group_by(User.id, User.first_name, User.last_name, College.name)
            .order_by(func.count(distinct(PodSubmission.question_id)).desc())
            .limit(limit)
        )
        result = await session.execute(q)
        return _rows_to_dicts(result.all())


# ── Difficulty & Language ─────────────────────────────────────────────────────

async def get_difficulty_breakdown(
    college_name: Optional[str] = None,
) -> list[dict]:
    """How many students solved easy/medium/hard problems."""
    logger.debug(f"get_difficulty_breakdown college={college_name}")
    async with get_session() as session:
        q = (
            select(
                PodSubmission.difficulty,
                func.count(distinct(PodSubmission.user_id)).label("students_attempted"),
                func.count(distinct(
                    case((PodSubmission.status == "pass", PodSubmission.user_id))
                )).label("students_passed"),
                func.round(
                    func.count(distinct(case((PodSubmission.status == "pass", PodSubmission.user_id))))
                    * 100.0
                    / func.nullif(func.count(distinct(PodSubmission.user_id)), 0),
                    2
                ).label("pass_rate_percent"),
            )
            .join(User, User.id == PodSubmission.user_id)
            .join(College, College.id == User.college_id)
            .where(
                PodSubmission.difficulty.isnot(None),
                User.role == "Student",
            )
        )
        if college_name:
            q = q.where(College.name.ilike(f"%{college_name}%"))
        q = q.group_by(PodSubmission.difficulty).order_by(PodSubmission.difficulty)
        result = await session.execute(q)
        return _rows_to_dicts(result.all())


async def get_language_breakdown(
    college_name: Optional[str] = None,
) -> list[dict]:
    """Which programming languages students are using."""
    logger.debug(f"get_language_breakdown college={college_name}")
    async with get_session() as session:
        q = (
            select(
                PodSubmission.language,
                func.count(distinct(PodSubmission.user_id)).label("students"),
                func.count(PodSubmission.id).label("total_submissions"),
                func.count(
                    case((PodSubmission.status == "pass", PodSubmission.id))
                ).label("passes"),
            )
            .join(User, User.id == PodSubmission.user_id)
            .join(College, College.id == User.college_id)
            .where(
                PodSubmission.language.isnot(None),
                User.role == "Student",
            )
        )
        if college_name:
            q = q.where(College.name.ilike(f"%{college_name}%"))
        q = (
            q.group_by(PodSubmission.language)
            .order_by(func.count(distinct(PodSubmission.user_id)).desc())
        )
        result = await session.execute(q)
        return _rows_to_dicts(result.all())


async def get_hard_solvers(
    college_name: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """Students who successfully solved hard PODs."""
    logger.debug(f"get_hard_solvers college={college_name}")
    async with get_session() as session:
        q = (
            select(
                (User.first_name + " " + User.last_name).label("name"),
                College.name.label("college"),
                func.count(distinct(PodSubmission.question_id)).label("hard_questions_solved"),
            )
            .join(PodSubmission, PodSubmission.user_id == User.id)
            .join(College, College.id == User.college_id)
            .where(
                PodSubmission.status == "pass",
                PodSubmission.difficulty == "hard",
                User.role == "Student",
            )
        )
        if college_name:
            q = q.where(College.name.ilike(f"%{college_name}%"))
        q = (
            q.group_by(User.id, User.first_name, User.last_name, College.name)
            .order_by(func.count(distinct(PodSubmission.question_id)).desc())
            .limit(limit)
        )
        result = await session.execute(q)
        return _rows_to_dicts(result.all())


# ── Streaks ───────────────────────────────────────────────────────────────────

async def get_longest_streaks(
    college_name: Optional[str] = None,
    limit: int = 10,
) -> list[dict]:
    """Students with the longest POD streaks (active or all-time)."""
    logger.debug(f"get_longest_streaks college={college_name}")
    async with get_session() as session:
        q = (
            select(
                (User.first_name + " " + User.last_name).label("name"),
                College.name.label("college"),
                func.max(PodStreak.streak_count).label("max_streak"),
                func.bool_or(PodStreak.is_active).label("has_active_streak"),
            )
            .join(PodStreak, PodStreak.user_id == User.id)
            .join(College, College.id == User.college_id)
            .where(User.role == "Student")
        )
        if college_name:
            q = q.where(College.name.ilike(f"%{college_name}%"))
        q = (
            q.group_by(User.id, User.first_name, User.last_name, College.name)
            .order_by(func.max(PodStreak.streak_count).desc())
            .limit(limit)
        )
        result = await session.execute(q)
        return _rows_to_dicts(result.all())


async def get_active_streaks(
    college_name: Optional[str] = None,
    min_streak: int = 3,
    limit: int = 20,
) -> list[dict]:
    """Students currently on an active streak."""
    logger.debug(f"get_active_streaks college={college_name} min={min_streak}")
    async with get_session() as session:
        q = (
            select(
                (User.first_name + " " + User.last_name).label("name"),
                College.name.label("college"),
                PodStreak.streak_count,
                PodStreak.start_date,
            )
            .join(PodStreak, PodStreak.user_id == User.id)
            .join(College, College.id == User.college_id)
            .where(
                PodStreak.is_active == True,
                PodStreak.streak_count >= min_streak,
                User.role == "Student",
            )
        )
        if college_name:
            q = q.where(College.name.ilike(f"%{college_name}%"))
        q = q.order_by(PodStreak.streak_count.desc()).limit(limit)
        result = await session.execute(q)
        return _rows_to_dicts(result.all())


async def get_lost_streaks(
    college_name: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """Students who recently lost their streak."""
    logger.debug(f"get_lost_streaks college={college_name}")
    last_week = _today_utc() - timedelta(days=7)
    async with get_session() as session:
        q = (
            select(
                (User.first_name + " " + User.last_name).label("name"),
                College.name.label("college"),
                PodStreak.streak_count.label("lost_streak_count"),
                func.date(PodStreak.end_date).label("lost_on"),
            )
            .join(PodStreak, PodStreak.user_id == User.id)
            .join(College, College.id == User.college_id)
            .where(
                PodStreak.is_active == False,
                func.date(PodStreak.end_date) >= last_week,
                User.role == "Student",
            )
        )
        if college_name:
            q = q.where(College.name.ilike(f"%{college_name}%"))
        q = q.order_by(PodStreak.streak_count.desc()).limit(limit)
        result = await session.execute(q)
        return _rows_to_dicts(result.all())


# ── Points & Coins ────────────────────────────────────────────────────────────

async def get_top_coins(
    college_name: Optional[str] = None,
    limit: int = 10,
) -> list[dict]:
    """Students with the most POD coins earned."""
    logger.debug(f"get_top_coins college={college_name}")
    async with get_session() as session:
        q = (
            select(
                (User.first_name + " " + User.last_name).label("name"),
                College.name.label("college"),
                func.sum(UserCoins.coins_count).label("total_coins"),
            )
            .join(UserCoins, UserCoins.user_id == User.id)
            .join(College, College.id == User.college_id)
            .where(User.role == "Student")
        )
        if college_name:
            q = q.where(College.name.ilike(f"%{college_name}%"))
        q = (
            q.group_by(User.id, User.first_name, User.last_name, College.name)
            .order_by(func.sum(UserCoins.coins_count).desc())
            .limit(limit)
        )
        result = await session.execute(q)
        return _rows_to_dicts(result.all())


async def get_total_points_today(college_name: Optional[str] = None) -> list[dict]:
    """Total points earned by students today."""
    logger.debug(f"get_total_points_today college={college_name}")
    today = _today_utc()
    async with get_session() as session:
        q = (
            select(
                College.name.label("college"),
                func.sum(PodSubmission.obtained_score).label("total_points_today"),
                func.count(distinct(PodSubmission.user_id)).label("students_participated"),
            )
            .join(User, User.id == PodSubmission.user_id)
            .join(College, College.id == User.college_id)
            .where(
                func.date(PodSubmission.create_at) == today,
                User.role == "Student",
            )
        )
        if college_name:
            q = q.where(College.name.ilike(f"%{college_name}%"))
        q = q.group_by(College.name).order_by(College.name)
        result = await session.execute(q)
        return _rows_to_dicts(result.all())


async def get_top_scorers(
    college_name: Optional[str] = None,
    limit: int = 10,
) -> list[dict]:
    """Students with the highest total POD score."""
    logger.debug(f"get_top_scorers college={college_name}")
    async with get_session() as session:
        q = (
            select(
                (User.first_name + " " + User.last_name).label("name"),
                College.name.label("college"),
                func.sum(PodSubmission.obtained_score).label("total_score"),
                func.count(distinct(PodSubmission.question_id)).label("questions_attempted"),
            )
            .join(PodSubmission, PodSubmission.user_id == User.id)
            .join(College, College.id == User.college_id)
            .where(User.role == "Student")
        )
        if college_name:
            q = q.where(College.name.ilike(f"%{college_name}%"))
        q = (
            q.group_by(User.id, User.first_name, User.last_name, College.name)
            .order_by(func.sum(PodSubmission.obtained_score).desc())
            .limit(limit)
        )
        result = await session.execute(q)
        return _rows_to_dicts(result.all())


# ── Badges ────────────────────────────────────────────────────────────────────

async def get_badge_earners(
    college_name: Optional[str] = None,
    limit: int = 500,
) -> list[dict]:
    """Students who have earned POD badges."""
    logger.debug(f"get_badge_earners college={college_name}")
    async with get_session() as session:
        q = (
            select(
                (User.first_name + " " + User.last_name).label("name"),
                College.name.label("college"),
                PodBadge.name.label("badge_name"),
                PodBadge.badge_type,
                UserPodBadge.create_at.label("earned_at"),
            )
            .join(UserPodBadge, UserPodBadge.user_id == User.id)
            .join(PodBadge, PodBadge.id == UserPodBadge.pod_badge_id)
            .join(College, College.id == User.college_id)
            .where(User.role == "Student")
        )
        if college_name:
            q = q.where(College.name.ilike(f"%{college_name}%"))
        q = q.order_by(UserPodBadge.create_at.desc()).limit(limit)
        result = await session.execute(q)
        return _rows_to_dicts(result.all())


async def get_weekly_badge_earners(
    college_name: Optional[str] = None,
    limit: int = 500,
) -> list[dict]:
    """Students who earned badges this week."""
    logger.debug(f"get_weekly_badge_earners college={college_name}")
    week_start = _today_utc() - timedelta(days=_today_utc().weekday())
    async with get_session() as session:
        q = (
            select(
                (User.first_name + " " + User.last_name).label("name"),
                College.name.label("college"),
                PodBadge.name.label("badge_name"),
                PodBadge.badge_type,
                UserPodBadge.create_at.label("earned_at"),
            )
            .join(UserPodBadge, UserPodBadge.user_id == User.id)
            .join(PodBadge, PodBadge.id == UserPodBadge.pod_badge_id)
            .join(College, College.id == User.college_id)
            .where(
                func.date(UserPodBadge.create_at) >= week_start,
                User.role == "Student",
            )
        )
        if college_name:
            q = q.where(College.name.ilike(f"%{college_name}%"))
        q = q.order_by(UserPodBadge.create_at.desc()).limit(limit)
        result = await session.execute(q)
        return _rows_to_dicts(result.all())