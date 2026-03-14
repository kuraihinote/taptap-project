# analytics.py — TapTap POD Analytics Chatbot
# All POD queries using SQLAlchemy + raw SQL via text().
# DB access: db = next(get_db()) matching reference project pattern.

from datetime import date, timedelta
from typing import Optional
from sqlalchemy import text
from db import get_db
from logger import logger


def _rows_to_dicts(rows) -> list[dict]:
    return [dict(r._mapping) for r in rows]


def get_who_solved_today(college_name: Optional[str] = None) -> list[dict]:
    try:
        db = next(get_db())
        params = {"today": date.today()}
        college_clause = ""
        if college_name:
            college_clause = "AND c.name ILIKE :college"
            params["college"] = f"%{college_name}%"
        result = db.execute(text(f"""
            SELECT u.first_name || ' ' || u.last_name AS name, u.email,
                   c.name AS college, ps.title, ps.difficulty,
                   ps.language, ps.obtained_score, ps.create_at
            FROM pod.pod_submission ps
            JOIN public.user u ON u.id = ps.user_id
            JOIN public.college c ON c.id = u.college_id
            WHERE ps.status = 'pass' AND ps.create_at::date = :today {college_clause}
            ORDER BY ps.create_at DESC
        """), params).fetchall()
        return _rows_to_dicts(result)
    except Exception as e:
        logger.error(f"get_who_solved_today error: {e}")
        return []


def get_attempt_count_today(college_name: Optional[str] = None) -> list[dict]:
    try:
        db = next(get_db())
        params = {"today": date.today()}
        college_clause = ""
        if college_name:
            college_clause = "AND c.name ILIKE :college"
            params["college"] = f"%{college_name}%"
        result = db.execute(text(f"""
            SELECT COUNT(DISTINCT pa.user_id) AS total_attempts,
                   COUNT(DISTINCT CASE WHEN ps.status='pass' THEN ps.user_id END) AS passed,
                   COUNT(DISTINCT CASE WHEN ps.status='fail' THEN ps.user_id END) AS failed
            FROM pod.pod_attempt pa
            JOIN public.user u ON u.id = pa.user_id
            JOIN public.college c ON c.id = u.college_id
            LEFT JOIN pod.pod_submission ps
                ON ps.user_id = pa.user_id
                AND ps.problem_of_the_day_id = pa.problem_of_the_day_id
            WHERE pa.create_at::date = :today {college_clause}
        """), params).fetchall()
        return _rows_to_dicts(result)
    except Exception as e:
        logger.error(f"get_attempt_count_today error: {e}")
        return []


def get_question_today() -> list[dict]:
    try:
        db = next(get_db())
        result = db.execute(text("""
            SELECT id, date, difficulty, type, unique_user_attempts, is_active
            FROM pod.problem_of_the_day
            WHERE date = (SELECT MAX(date) FROM pod.problem_of_the_day)
        """)).fetchall()
        return _rows_to_dicts(result)
    except Exception as e:
        logger.error(f"get_question_today error: {e}")
        return []


def get_fastest_solvers(college_name: Optional[str] = None, limit: int = 10) -> list[dict]:
    try:
        db = next(get_db())
        params = {"today": date.today(), "limit": limit}
        college_clause = ""
        if college_name:
            college_clause = "AND c.name ILIKE :college"
            params["college"] = f"%{college_name}%"
        result = db.execute(text(f"""
            SELECT u.first_name || ' ' || u.last_name AS name,
                   c.name AS college, ROUND(pa.time_taken / 1000.0, 1) AS time_taken_seconds,
                   pa.pod_started_at, pa.end_date
            FROM pod.pod_attempt pa
            JOIN public.user u ON u.id = pa.user_id
            JOIN public.college c ON c.id = u.college_id
            WHERE pa.create_at::date = :today AND pa.status = 'completed'
              AND pa.time_taken IS NOT NULL {college_clause}
            ORDER BY pa.time_taken ASC LIMIT :limit
        """), params).fetchall()
        return _rows_to_dicts(result)
    except Exception as e:
        logger.error(f"get_fastest_solvers error: {e}")
        return []


def get_not_attempted_today(college_name: Optional[str] = None, limit: int = 20) -> list[dict]:
    try:
        db = next(get_db())
        params = {"today": date.today(), "limit": limit}
        college_clause = ""
        if college_name:
            college_clause = "AND c.name ILIKE :college"
            params["college"] = f"%{college_name}%"
        result = db.execute(text(f"""
            SELECT u.first_name || ' ' || u.last_name AS name, u.email, c.name AS college
            FROM public.user u
            JOIN public.college c ON c.id = u.college_id
            WHERE u.role = 'Student' {college_clause}
              AND u.id NOT IN (SELECT user_id FROM pod.pod_attempt WHERE create_at::date = :today)
            ORDER BY u.first_name LIMIT :limit
        """), params).fetchall()
        return _rows_to_dicts(result)
    except Exception as e:
        logger.error(f"get_not_attempted_today error: {e}")
        return []


def get_pass_fail_summary(college_name: Optional[str] = None, date_filter: Optional[str] = None, limit: int = 20) -> list[dict]:
    try:
        db = next(get_db())
        params = {"limit": limit}
        date_clause = ""
        if date_filter == "today":
            date_clause = "AND ps.create_at::date = CURRENT_DATE"
        elif date_filter:
            date_clause = f"AND ps.create_at::date = '{date_filter}'"
        college_clause = ""
        if college_name:
            college_clause = "AND c.name ILIKE :college"
            params["college"] = f"%{college_name}%"
        result = db.execute(text(f"""
            SELECT u.first_name || ' ' || u.last_name AS name, c.name AS college,
                   COUNT(DISTINCT CASE WHEN ps.status='pass' THEN ps.question_id END) AS pass_count,
                   COUNT(DISTINCT CASE WHEN ps.status='fail' THEN ps.question_id END) AS fail_count,
                   COUNT(DISTINCT ps.question_id) AS total_questions
            FROM pod.pod_submission ps
            JOIN public.user u ON u.id = ps.user_id
            JOIN public.college c ON c.id = u.college_id
            WHERE u.role = 'Student' {date_clause} {college_clause}
            GROUP BY u.id, u.first_name, u.last_name, c.name
            ORDER BY pass_count DESC LIMIT :limit
        """), params).fetchall()
        return _rows_to_dicts(result)
    except Exception as e:
        logger.error(f"get_pass_fail_summary error: {e}")
        return []


def get_pass_rate(college_name: Optional[str] = None) -> list[dict]:
    try:
        db = next(get_db())
        params = {}
        college_clause = ""
        if college_name:
            college_clause = "AND c.name ILIKE :college"
            params["college"] = f"%{college_name}%"
        result = db.execute(text(f"""
            SELECT c.name AS college,
                   COUNT(DISTINCT CASE WHEN ps.status='pass' THEN ps.id END) AS total_passes,
                   COUNT(DISTINCT ps.id) AS total_submissions,
                   ROUND(COUNT(DISTINCT CASE WHEN ps.status='pass' THEN ps.id END)*100.0
                         / NULLIF(COUNT(DISTINCT ps.id),0), 2) AS pass_rate_percent
            FROM pod.pod_submission ps
            JOIN public.user u ON u.id = ps.user_id
            JOIN public.college c ON c.id = u.college_id
            WHERE u.role = 'Student' {college_clause}
            GROUP BY c.name ORDER BY c.name
        """), params).fetchall()
        return _rows_to_dicts(result)
    except Exception as e:
        logger.error(f"get_pass_rate error: {e}")
        return []


def get_top_passers(college_name: Optional[str] = None, limit: int = 10) -> list[dict]:
    try:
        db = next(get_db())
        params = {"limit": limit}
        college_clause = ""
        if college_name:
            college_clause = "AND c.name ILIKE :college"
            params["college"] = f"%{college_name}%"
        result = db.execute(text(f"""
            SELECT u.first_name || ' ' || u.last_name AS name, c.name AS college,
                   COUNT(DISTINCT ps.question_id) AS questions_passed,
                   SUM(ps.obtained_score) AS total_score
            FROM pod.pod_submission ps
            JOIN public.user u ON u.id = ps.user_id
            JOIN public.college c ON c.id = u.college_id
            WHERE ps.status = 'pass' AND u.role = 'Student' {college_clause}
            GROUP BY u.id, u.first_name, u.last_name, c.name
            ORDER BY questions_passed DESC LIMIT :limit
        """), params).fetchall()
        return _rows_to_dicts(result)
    except Exception as e:
        logger.error(f"get_top_passers error: {e}")
        return []


def get_never_passed(college_name: Optional[str] = None, limit: int = 20) -> list[dict]:
    try:
        db = next(get_db())
        params = {"limit": limit}
        college_clause = ""
        if college_name:
            college_clause = "AND c.name ILIKE :college"
            params["college"] = f"%{college_name}%"
        result = db.execute(text(f"""
            SELECT u.first_name || ' ' || u.last_name AS name, u.email, c.name AS college
            FROM public.user u
            JOIN public.college c ON c.id = u.college_id
            WHERE u.role = 'Student' {college_clause}
              AND u.id IN (SELECT DISTINCT user_id FROM pod.pod_submission)
              AND u.id NOT IN (SELECT DISTINCT user_id FROM pod.pod_submission WHERE status='pass')
            ORDER BY u.first_name LIMIT :limit
        """), params).fetchall()
        return _rows_to_dicts(result)
    except Exception as e:
        logger.error(f"get_never_passed error: {e}")
        return []


def get_weekly_passers(college_name: Optional[str] = None, limit: int = 20) -> list[dict]:
    try:
        db = next(get_db())
        week_start = date.today() - timedelta(days=date.today().weekday())
        params = {"week_start": week_start, "limit": limit}
        college_clause = ""
        if college_name:
            college_clause = "AND c.name ILIKE :college"
            params["college"] = f"%{college_name}%"
        result = db.execute(text(f"""
            SELECT u.first_name || ' ' || u.last_name AS name, c.name AS college,
                   COUNT(DISTINCT ps.question_id) AS questions_passed_this_week
            FROM pod.pod_submission ps
            JOIN public.user u ON u.id = ps.user_id
            JOIN public.college c ON c.id = u.college_id
            WHERE ps.status = 'pass' AND ps.create_at::date >= :week_start
              AND u.role = 'Student' {college_clause}
            GROUP BY u.id, u.first_name, u.last_name, c.name
            ORDER BY questions_passed_this_week DESC LIMIT :limit
        """), params).fetchall()
        return _rows_to_dicts(result)
    except Exception as e:
        logger.error(f"get_weekly_passers error: {e}")
        return []


def get_difficulty_breakdown(college_name: Optional[str] = None) -> list[dict]:
    try:
        db = next(get_db())
        params = {}
        college_clause = ""
        if college_name:
            college_clause = "AND c.name ILIKE :college"
            params["college"] = f"%{college_name}%"
        result = db.execute(text(f"""
            SELECT ps.difficulty,
                   COUNT(DISTINCT ps.user_id) AS students_attempted,
                   COUNT(DISTINCT CASE WHEN ps.status='pass' THEN ps.user_id END) AS students_passed,
                   ROUND(COUNT(DISTINCT CASE WHEN ps.status='pass' THEN ps.user_id END)*100.0
                         / NULLIF(COUNT(DISTINCT ps.user_id),0), 2) AS pass_rate_percent
            FROM pod.pod_submission ps
            JOIN public.user u ON u.id = ps.user_id
            JOIN public.college c ON c.id = u.college_id
            WHERE ps.difficulty IS NOT NULL AND u.role = 'Student' {college_clause}
            GROUP BY ps.difficulty ORDER BY ps.difficulty
        """), params).fetchall()
        return _rows_to_dicts(result)
    except Exception as e:
        logger.error(f"get_difficulty_breakdown error: {e}")
        return []


def get_language_breakdown(college_name: Optional[str] = None) -> list[dict]:
    try:
        db = next(get_db())
        params = {}
        college_clause = ""
        if college_name:
            college_clause = "AND c.name ILIKE :college"
            params["college"] = f"%{college_name}%"
        result = db.execute(text(f"""
            SELECT ps.language,
                   COUNT(DISTINCT ps.user_id) AS students,
                   COUNT(ps.id) AS total_submissions,
                   COUNT(CASE WHEN ps.status='pass' THEN 1 END) AS passes
            FROM pod.pod_submission ps
            JOIN public.user u ON u.id = ps.user_id
            JOIN public.college c ON c.id = u.college_id
            WHERE ps.language IS NOT NULL AND u.role = 'Student' {college_clause}
            GROUP BY ps.language ORDER BY students DESC
        """), params).fetchall()
        return _rows_to_dicts(result)
    except Exception as e:
        logger.error(f"get_language_breakdown error: {e}")
        return []


def get_hard_solvers(college_name: Optional[str] = None, limit: int = 20) -> list[dict]:
    try:
        db = next(get_db())
        params = {"limit": limit}
        college_clause = ""
        if college_name:
            college_clause = "AND c.name ILIKE :college"
            params["college"] = f"%{college_name}%"
        result = db.execute(text(f"""
            SELECT u.first_name || ' ' || u.last_name AS name, c.name AS college,
                   COUNT(DISTINCT ps.question_id) AS hard_questions_solved
            FROM pod.pod_submission ps
            JOIN public.user u ON u.id = ps.user_id
            JOIN public.college c ON c.id = u.college_id
            WHERE ps.status = 'pass' AND ps.difficulty = 'hard'
              AND u.role = 'Student' {college_clause}
            GROUP BY u.id, u.first_name, u.last_name, c.name
            ORDER BY hard_questions_solved DESC LIMIT :limit
        """), params).fetchall()
        return _rows_to_dicts(result)
    except Exception as e:
        logger.error(f"get_hard_solvers error: {e}")
        return []


def get_longest_streaks(college_name: Optional[str] = None, limit: int = 10) -> list[dict]:
    try:
        db = next(get_db())
        params = {"limit": limit}
        college_clause = ""
        if college_name:
            college_clause = "AND c.name ILIKE :college"
            params["college"] = f"%{college_name}%"
        result = db.execute(text(f"""
            SELECT u.first_name || ' ' || u.last_name AS name, c.name AS college,
                   MAX(ps.streak_count) AS max_streak,
                   BOOL_OR(ps.is_active) AS has_active_streak
            FROM pod.pod_streak ps
            JOIN public.user u ON u.id = ps.user_id
            JOIN public.college c ON c.id = u.college_id
            WHERE u.role = 'Student' {college_clause}
            GROUP BY u.id, u.first_name, u.last_name, c.name
            ORDER BY max_streak DESC LIMIT :limit
        """), params).fetchall()
        return _rows_to_dicts(result)
    except Exception as e:
        logger.error(f"get_longest_streaks error: {e}")
        return []


def get_active_streaks(college_name: Optional[str] = None, min_streak: int = 3, limit: int = 20) -> list[dict]:
    try:
        db = next(get_db())
        params = {"min_streak": min_streak, "limit": limit}
        college_clause = ""
        if college_name:
            college_clause = "AND c.name ILIKE :college"
            params["college"] = f"%{college_name}%"
        result = db.execute(text(f"""
            SELECT u.first_name || ' ' || u.last_name AS name, c.name AS college,
                   ps.streak_count, ps.start_date
            FROM pod.pod_streak ps
            JOIN public.user u ON u.id = ps.user_id
            JOIN public.college c ON c.id = u.college_id
            WHERE ps.is_active = true AND ps.streak_count >= :min_streak
              AND u.role = 'Student' {college_clause}
            ORDER BY ps.streak_count DESC LIMIT :limit
        """), params).fetchall()
        return _rows_to_dicts(result)
    except Exception as e:
        logger.error(f"get_active_streaks error: {e}")
        return []


def get_lost_streaks(college_name: Optional[str] = None, limit: int = 20) -> list[dict]:
    try:
        db = next(get_db())
        last_week = date.today() - timedelta(days=7)
        params = {"last_week": last_week, "limit": limit}
        college_clause = ""
        if college_name:
            college_clause = "AND c.name ILIKE :college"
            params["college"] = f"%{college_name}%"
        result = db.execute(text(f"""
            SELECT u.first_name || ' ' || u.last_name AS name, c.name AS college,
                   ps.streak_count AS lost_streak_count, ps.end_date::date AS lost_on
            FROM pod.pod_streak ps
            JOIN public.user u ON u.id = ps.user_id
            JOIN public.college c ON c.id = u.college_id
            WHERE ps.is_active = false AND ps.end_date::date >= :last_week
              AND u.role = 'Student' {college_clause}
            ORDER BY ps.streak_count DESC LIMIT :limit
        """), params).fetchall()
        return _rows_to_dicts(result)
    except Exception as e:
        logger.error(f"get_lost_streaks error: {e}")
        return []


def get_top_coins(college_name: Optional[str] = None, limit: int = 10) -> list[dict]:
    try:
        db = next(get_db())
        params = {"limit": limit}
        college_clause = ""
        if college_name:
            college_clause = "AND c.name ILIKE :college"
            params["college"] = f"%{college_name}%"
        result = db.execute(text(f"""
            SELECT u.first_name || ' ' || u.last_name AS name, c.name AS college,
                   SUM(uc.coins_count) AS total_coins
            FROM pod.user_coins uc
            JOIN public.user u ON u.id = uc.user_id
            JOIN public.college c ON c.id = u.college_id
            WHERE u.role = 'Student' {college_clause}
            GROUP BY u.id, u.first_name, u.last_name, c.name
            ORDER BY total_coins DESC LIMIT :limit
        """), params).fetchall()
        return _rows_to_dicts(result)
    except Exception as e:
        logger.error(f"get_top_coins error: {e}")
        return []


def get_total_points_today(college_name: Optional[str] = None) -> list[dict]:
    try:
        db = next(get_db())
        params = {"today": date.today()}
        college_clause = ""
        if college_name:
            college_clause = "AND c.name ILIKE :college"
            params["college"] = f"%{college_name}%"
        result = db.execute(text(f"""
            SELECT c.name AS college,
                   SUM(ps.obtained_score) AS total_points_today,
                   COUNT(DISTINCT ps.user_id) AS students_participated
            FROM pod.pod_submission ps
            JOIN public.user u ON u.id = ps.user_id
            JOIN public.college c ON c.id = u.college_id
            WHERE ps.create_at::date = :today AND u.role = 'Student' {college_clause}
            GROUP BY c.name
        """), params).fetchall()
        return _rows_to_dicts(result)
    except Exception as e:
        logger.error(f"get_total_points_today error: {e}")
        return []


def get_top_scorers(
    college_name: Optional[str] = None,
    limit: int = 10,
    week_filter: Optional[bool] = None,
) -> list[dict]:
    try:
        db = next(get_db())
        params = {"limit": limit}
        college_clause = ""
        week_clause = ""
        if college_name:
            college_clause = "AND c.name ILIKE :college"
            params["college"] = f"%{college_name}%"
        if week_filter:
            week_clause = "AND ps.create_at::date >= date_trunc('week', CURRENT_DATE)"
        result = db.execute(text(f"""
            SELECT u.first_name || ' ' || u.last_name AS name, c.name AS college,
                   SUM(ps.obtained_score) AS total_score,
                   COUNT(DISTINCT ps.question_id) AS questions_attempted
            FROM pod.pod_submission ps
            JOIN public.user u ON u.id = ps.user_id
            JOIN public.college c ON c.id = u.college_id
            WHERE u.role = 'Student' {college_clause} {week_clause}
            GROUP BY u.id, u.first_name, u.last_name, c.name
            ORDER BY total_score DESC LIMIT :limit
        """), params).fetchall()
        return _rows_to_dicts(result)
    except Exception as e:
        logger.error(f"get_top_scorers error: {e}")
        return []


def get_badge_earners(college_name: Optional[str] = None, limit: int = 20) -> list[dict]:
    try:
        db = next(get_db())
        params = {"limit": limit}
        college_clause = ""
        if college_name:
            college_clause = "AND c.name ILIKE :college"
            params["college"] = f"%{college_name}%"
        result = db.execute(text(f"""
            SELECT u.first_name || ' ' || u.last_name AS name, c.name AS college,
                   pb.name AS badge_name, pb.badge_type, upb.create_at AS earned_at
            FROM pod.user_pod_badge upb
            JOIN public.user u ON u.id = upb.user_id
            JOIN pod.pod_badge pb ON pb.id = upb.pod_badge_id
            JOIN public.college c ON c.id = u.college_id
            WHERE u.role = 'Student' {college_clause}
            ORDER BY upb.create_at DESC LIMIT :limit
        """), params).fetchall()
        return _rows_to_dicts(result)
    except Exception as e:
        logger.error(f"get_badge_earners error: {e}")
        return []


def get_weekly_badge_earners(college_name: Optional[str] = None, limit: int = 20) -> list[dict]:
    try:
        db = next(get_db())
        week_start = date.today() - timedelta(days=date.today().weekday())
        params = {"week_start": week_start, "limit": limit}
        college_clause = ""
        if college_name:
            college_clause = "AND c.name ILIKE :college"
            params["college"] = f"%{college_name}%"
        result = db.execute(text(f"""
            SELECT u.first_name || ' ' || u.last_name AS name, c.name AS college,
                   pb.name AS badge_name, pb.badge_type, upb.create_at AS earned_at
            FROM pod.user_pod_badge upb
            JOIN public.user u ON u.id = upb.user_id
            JOIN pod.pod_badge pb ON pb.id = upb.pod_badge_id
            JOIN public.college c ON c.id = u.college_id
            WHERE upb.create_at::date >= :week_start AND u.role = 'Student' {college_clause}
            ORDER BY upb.create_at DESC LIMIT :limit
        """), params).fetchall()
        return _rows_to_dicts(result)
    except Exception as e:
        logger.error(f"get_weekly_badge_earners error: {e}")
        return []


def get_student_profile(
    student_name: str,
    college_name: Optional[str] = None,
    date_filter: Optional[str] = None,
    info_type: str = "all",
    language: Optional[str] = None,
    week_filter: Optional[bool] = None,
    pod_type: Optional[str] = None,
) -> dict:
    """Full student POD profile — submissions, streaks, badges, coins."""
    try:
        db = next(get_db())

        # Build date clause
        if date_filter == "today":
            date_clause = "AND ps.create_at::date = CURRENT_DATE"
        elif date_filter:
            date_clause = f"AND ps.create_at::date = '{date_filter}'"
        elif week_filter:
            date_clause = "AND ps.create_at::date >= date_trunc('week', CURRENT_DATE)"
        else:
            date_clause = ""

        # Initialize params first
        params = {
            "student_name": f"%{student_name}%",
        }
        if college_name:
            params["college"] = f"%{college_name}%"

        college_clause = "AND c.name ILIKE :college" if college_name else ""
        name_clause = "AND (u.first_name || ' ' || u.last_name) ILIKE :student_name"

        # Build language clause
        language_clause = ""
        if language:
            params["language"] = f"%{language}%"
            language_clause = "AND ps.language ILIKE :language"

        # Build pod_type clause — joins to problem_of_the_day to filter by coding/aptitude/verbal
        pod_type_join = ""
        pod_type_clause = ""
        if pod_type:
            params["pod_type"] = pod_type.lower()
            pod_type_join = "JOIN pod.problem_of_the_day potd ON potd.id = ps.problem_of_the_day_id"
            pod_type_clause = "AND potd.type = :pod_type"

        result = {}

        # Normalize info_type — handle combined values like "streaks, badges"
        info_types = [i.strip() for i in info_type.replace(" and ", ",").split(",")]
        def should_fetch(section):
            return "all" in info_types or section in info_types

        # ── Submissions ───────────────────────────────────────────────────
        if should_fetch("submissions"):
            rows = db.execute(text(f"""
                SELECT u.first_name || ' ' || u.last_name AS name,
                       u.email, c.name AS college,
                       ps.title, ps.language, ps.difficulty,
                       ps.status, ps.obtained_score, ps.pod_coins,
                       ps.create_at
                FROM pod.pod_submission ps
                JOIN public.user u ON u.id = ps.user_id
                JOIN public.college c ON c.id = u.college_id
                {pod_type_join}
                WHERE u.role = 'Student'
                  {name_clause}
                  {college_clause}
                  {date_clause}
                  {language_clause}
                  {pod_type_clause}
                ORDER BY ps.create_at DESC
                LIMIT 20
            """), params).fetchall()
            result["submissions"] = _rows_to_dicts(rows)

        # ── Streaks ───────────────────────────────────────────────────────
        if should_fetch("streaks"):
            rows = db.execute(text(f"""
                SELECT u.first_name || ' ' || u.last_name AS name,
                       c.name AS college,
                       ps.type, ps.streak_count,
                       ps.is_active, ps.start_date, ps.end_date
                FROM pod.pod_streak ps
                JOIN public.user u ON u.id = ps.user_id
                JOIN public.college c ON c.id = u.college_id
                WHERE u.role = 'Student'
                  {name_clause}
                  {college_clause}
                ORDER BY ps.streak_count DESC
            """), params).fetchall()
            result["streaks"] = _rows_to_dicts(rows)

        # ── Badges ────────────────────────────────────────────────────────
        if should_fetch("badges"):
            rows = db.execute(text(f"""
                SELECT u.first_name || ' ' || u.last_name AS name,
                       c.name AS college,
                       pb.name AS badge_name,
                       pb.description, pb.badge_type, pb.pod_category,
                       upb.create_at AS earned_at
                FROM pod.user_pod_badge upb
                JOIN public.user u ON u.id = upb.user_id
                JOIN pod.pod_badge pb ON pb.id = upb.pod_badge_id
                JOIN public.college c ON c.id = u.college_id
                WHERE u.role = 'Student'
                  {name_clause}
                  {college_clause}
                ORDER BY upb.create_at DESC
            """), params).fetchall()
            result["badges"] = _rows_to_dicts(rows)

        # ── Coins ─────────────────────────────────────────────────────────
        if should_fetch("coins"):
            rows = db.execute(text(f"""
                SELECT u.first_name || ' ' || u.last_name AS name,
                       c.name AS college,
                       SUM(uc.coins_count) AS total_coins,
                       COUNT(uc.id) AS total_transactions
                FROM pod.user_coins uc
                JOIN public.user u ON u.id = uc.user_id
                JOIN public.college c ON c.id = u.college_id
                WHERE u.role = 'Student'
                  {name_clause}
                  {college_clause}
                GROUP BY u.id, u.first_name, u.last_name, c.name
            """), params).fetchall()
            result["coins"] = _rows_to_dicts(rows)

        return result

    except Exception as e:
        logger.error(f"get_student_profile error: {e}")
        return {}

# ══════════════════════════════════════════════════════════════════════════════
# EMPLOYABILITY TRACK
# ══════════════════════════════════════════════════════════════════════════════


def get_emp_top_scorers(
    college_name: Optional[str] = None,
    limit: int = 10,
    week_filter: Optional[bool] = None,
) -> list[dict]:
    """Students ranked by total obtained_score across all employability submissions."""
    try:
        db = next(get_db())
        params: dict = {"limit": limit}
        college_clause = ""
        week_clause = ""
        if college_name:
            college_clause = "AND c.name ILIKE :college"
            params["college"] = f"%{college_name}%"
        if week_filter:
            week_clause = "AND ets.create_at >= date_trunc('week', CURRENT_TIMESTAMP)"
        result = db.execute(text(f"""
            SELECT
                u.first_name || ' ' || u.last_name AS name,
                u.email,
                c.name                              AS college,
                COUNT(ets.id)                       AS total_submissions,
                SUM(ets.obtained_score)             AS total_score,
                COUNT(CASE WHEN ets.status = 'pass' THEN 1 END) AS total_passed
            FROM employability_track.employability_track_submission ets
            JOIN public.user    u ON u.id  = ets.user_id
            JOIN public.college c ON c.id  = u.college_id
            WHERE 1=1 {college_clause} {week_clause}
            GROUP BY u.id, u.first_name, u.last_name, u.email, c.name
            ORDER BY total_score DESC
            LIMIT :limit
        """), params).fetchall()
        return _rows_to_dicts(result)
    except Exception as e:
        logger.error(f"get_emp_top_scorers error: {e}")
        return []


def get_emp_difficulty_stats(
    college_name: Optional[str] = None,
) -> list[dict]:
    """Pass rate and submission counts grouped by difficulty (easy/medium/hard)."""
    try:
        db = next(get_db())
        params: dict = {}
        college_clause = ""
        if college_name:
            college_clause = "AND c.name ILIKE :college"
            params["college"] = f"%{college_name}%"
        result = db.execute(text(f"""
            SELECT
                ets.difficulty,
                COUNT(ets.id)                                            AS total_submissions,
                COUNT(DISTINCT ets.user_id)                              AS unique_students,
                COUNT(CASE WHEN ets.status = 'pass' THEN 1 END)         AS passed,
                COUNT(CASE WHEN ets.status = 'fail' THEN 1 END)         AS failed,
                ROUND(
                    COUNT(CASE WHEN ets.status = 'pass' THEN 1 END)*100.0
                    / NULLIF(COUNT(ets.id), 0), 2
                )                                                        AS pass_rate_percent
            FROM employability_track.employability_track_submission ets
            JOIN public.user    u ON u.id = ets.user_id
            JOIN public.college c ON c.id = u.college_id
            WHERE ets.difficulty IS NOT NULL {college_clause}
            GROUP BY ets.difficulty
            ORDER BY CASE ets.difficulty
                WHEN 'easy'   THEN 1
                WHEN 'medium' THEN 2
                WHEN 'hard'   THEN 3
                ELSE 4
            END
        """), params).fetchall()
        return _rows_to_dicts(result)
    except Exception as e:
        logger.error(f"get_emp_difficulty_stats error: {e}")
        return []


def get_emp_language_stats(
    college_name: Optional[str] = None,
) -> list[dict]:
    """Most-used programming languages in employability submissions with pass rates."""
    try:
        db = next(get_db())
        params: dict = {}
        college_clause = ""
        if college_name:
            college_clause = "AND c.name ILIKE :college"
            params["college"] = f"%{college_name}%"
        result = db.execute(text(f"""
            SELECT
                ets.language,
                COUNT(ets.id)                                            AS total_submissions,
                COUNT(DISTINCT ets.user_id)                              AS unique_students,
                COUNT(CASE WHEN ets.status = 'pass' THEN 1 END)         AS passed,
                ROUND(
                    COUNT(CASE WHEN ets.status = 'pass' THEN 1 END)*100.0
                    / NULLIF(COUNT(ets.id), 0), 2
                )                                                        AS pass_rate_percent
            FROM employability_track.employability_track_submission ets
            JOIN public.user    u ON u.id = ets.user_id
            JOIN public.college c ON c.id = u.college_id
            WHERE ets.language IS NOT NULL {college_clause}
            GROUP BY ets.language
            ORDER BY total_submissions DESC
        """), params).fetchall()
        return _rows_to_dicts(result)
    except Exception as e:
        logger.error(f"get_emp_language_stats error: {e}")
        return []


def get_emp_domain_breakdown(
    college_name: Optional[str] = None,
    domain_name: Optional[str] = None,
) -> list[dict]:
    """Submission counts and pass rates grouped by domain name. Optionally filter to a specific domain."""
    try:
        db = next(get_db())
        params: dict = {}
        college_clause = ""
        domain_clause = ""
        if college_name:
            college_clause = "AND c.name ILIKE :college"
            params["college"] = f"%{college_name}%"
        if domain_name:
            domain_clause = "AND d.domain ILIKE :domain"
            params["domain"] = f"%{domain_name}%"
        result = db.execute(text(f"""
            SELECT
                d.domain                                                 AS domain,
                COUNT(ets.id)                                            AS total_submissions,
                COUNT(DISTINCT ets.user_id)                              AS unique_students,
                COUNT(CASE WHEN ets.status = 'pass' THEN 1 END)         AS passed,
                ROUND(
                    COUNT(CASE WHEN ets.status = 'pass' THEN 1 END)*100.0
                    / NULLIF(COUNT(ets.id), 0), 2
                )                                                        AS pass_rate_percent
            FROM employability_track.employability_track_submission ets
            JOIN public.domains  d ON d.id  = ets.domain_id
            JOIN public.user     u ON u.id  = ets.user_id
            JOIN public.college  c ON c.id  = u.college_id
            WHERE 1=1 {college_clause} {domain_clause}
            GROUP BY d.domain
            ORDER BY total_submissions DESC
        """), params).fetchall()
        return _rows_to_dicts(result)
    except Exception as e:
        logger.error(f"get_emp_domain_breakdown error: {e}")
        return []


def get_emp_subdomain_breakdown(
    college_name: Optional[str] = None,
    domain_name: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """Submission counts and pass rates grouped by sub-domain topic name."""
    try:
        db = next(get_db())
        params: dict = {"limit": limit}
        college_clause = ""
        domain_clause = ""
        if college_name:
            college_clause = "AND c.name ILIKE :college"
            params["college"] = f"%{college_name}%"
        if domain_name:
            domain_clause = "AND d.domain ILIKE :domain"
            params["domain"] = f"%{domain_name}%"
        result = db.execute(text(f"""
            SELECT
                d.domain                                                 AS domain,
                qsd.name                                                 AS sub_domain,
                COUNT(ets.id)                                            AS total_submissions,
                COUNT(DISTINCT ets.user_id)                              AS unique_students,
                COUNT(CASE WHEN ets.status = 'pass' THEN 1 END)         AS passed,
                ROUND(
                    COUNT(CASE WHEN ets.status = 'pass' THEN 1 END)*100.0
                    / NULLIF(COUNT(ets.id), 0), 2
                )                                                        AS pass_rate_percent
            FROM employability_track.employability_track_submission ets
            JOIN public.domains           d   ON d.id   = ets.domain_id
            JOIN public.question_sub_domain qsd ON qsd.id = ets.sub_domain_id
            JOIN public.user               u   ON u.id   = ets.user_id
            JOIN public.college            c   ON c.id   = u.college_id
            WHERE 1=1 {college_clause} {domain_clause}
            GROUP BY d.domain, qsd.name
            ORDER BY total_submissions DESC
            LIMIT :limit
        """), params).fetchall()
        return _rows_to_dicts(result)
    except Exception as e:
        logger.error(f"get_emp_subdomain_breakdown error: {e}")
        return []


def get_emp_question_type_stats(
    college_name: Optional[str] = None,
) -> list[dict]:
    """Submission counts and pass rates by question type name (via public.test_type join)."""
    try:
        db = next(get_db())
        params: dict = {}
        college_clause = ""
        if college_name:
            college_clause = "AND c.name ILIKE :college"
            params["college"] = f"%{college_name}%"
        result = db.execute(text(f"""
            SELECT
                tt.name                                                  AS question_type,
                COUNT(ets.id)                                            AS total_submissions,
                COUNT(DISTINCT ets.user_id)                              AS unique_students,
                COUNT(CASE WHEN ets.status = 'pass' THEN 1 END)         AS passed,
                ROUND(
                    COUNT(CASE WHEN ets.status = 'pass' THEN 1 END)*100.0
                    / NULLIF(COUNT(ets.id), 0), 2
                )                                                        AS pass_rate_percent,
                ROUND(AVG(ets.obtained_score), 2)                       AS avg_score
            FROM employability_track.employability_track_submission ets
            JOIN employability_track.employability_track_question etq
                ON etq.question_id = ets.question_id
            JOIN public.test_type tt ON tt.id = etq.test_type_id
            JOIN public.user       u  ON u.id  = ets.user_id
            JOIN public.college    c  ON c.id  = u.college_id
            WHERE 1=1 {college_clause}
            GROUP BY tt.name
            ORDER BY total_submissions DESC
        """), params).fetchall()
        return _rows_to_dicts(result)
    except Exception as e:
        logger.error(f"get_emp_question_type_stats error: {e}")
        return []


def get_emp_most_solved(
    college_name: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """Students with the most questions marked 'solved' in question_status."""
    try:
        db = next(get_db())
        params: dict = {"limit": limit}
        college_clause = ""
        if college_name:
            college_clause = "AND c.name ILIKE :college"
            params["college"] = f"%{college_name}%"
        result = db.execute(text(f"""
            SELECT
                u.first_name || ' ' || u.last_name  AS name,
                u.email,
                c.name                              AS college,
                COUNT(CASE WHEN qs.status = 'solved'    THEN 1 END) AS solved_count,
                COUNT(CASE WHEN qs.status = 'attempted' THEN 1 END) AS attempted_count,
                COUNT(qs.question_id)               AS total_questions
            FROM employability_track.question_status qs
            JOIN public.user    u ON u.id = qs.user_id
            JOIN public.college c ON c.id = u.college_id
            WHERE 1=1 {college_clause}
            GROUP BY u.id, u.first_name, u.last_name, u.email, c.name
            ORDER BY solved_count DESC
            LIMIT :limit
        """), params).fetchall()
        return _rows_to_dicts(result)
    except Exception as e:
        logger.error(f"get_emp_most_solved error: {e}")
        return []


def get_emp_recent_activity(
    college_name: Optional[str] = None,
    limit: int = 20,
    date_filter: Optional[str] = None,
    days: Optional[int] = None,
    difficulty: Optional[str] = None,
    language: Optional[str] = None,
) -> list[dict]:
    """Latest employability submissions with optional filters for college, difficulty, language, date/days."""
    try:
        db = next(get_db())
        params: dict = {"limit": limit}
        college_clause = ""
        date_clause = ""
        difficulty_clause = ""
        language_clause = ""
        if college_name:
            college_clause = "AND c.name ILIKE :college"
            params["college"] = f"%{college_name}%"
        if date_filter == "today":
            date_clause = "AND ets.create_at::date = CURRENT_DATE"
        elif date_filter:
            date_clause = f"AND ets.create_at::date = '{date_filter}'"
        elif days:
            date_clause = "AND ets.create_at >= NOW() - (:days * INTERVAL '1 day')"
            params["days"] = days
        if difficulty:
            difficulty_clause = "AND ets.difficulty ILIKE :difficulty"
            params["difficulty"] = difficulty
        if language:
            language_clause = "AND ets.language ILIKE :language"
            params["language"] = f"%{language}%"
        result = db.execute(text(f"""
            SELECT
                u.first_name || ' ' || u.last_name  AS name,
                u.email,
                c.name          AS college,
                d.domain        AS domain,
                qsd.name        AS sub_domain,
                ets.difficulty,
                ets.language,
                ets.status,
                ets.obtained_score,
                ets.create_at
            FROM employability_track.employability_track_submission ets
            JOIN public.user               u   ON u.id   = ets.user_id
            JOIN public.college            c   ON c.id   = u.college_id
            LEFT JOIN public.domains       d   ON d.id   = ets.domain_id
            LEFT JOIN public.question_sub_domain qsd ON qsd.id = ets.sub_domain_id
            WHERE 1=1 {college_clause} {date_clause} {difficulty_clause} {language_clause}
            ORDER BY ets.create_at DESC
            LIMIT :limit
        """), params).fetchall()
        return _rows_to_dicts(result)
    except Exception as e:
        logger.error(f"get_emp_recent_activity error: {e}")
        return []


def get_emp_hardest_questions(
    college_name: Optional[str] = None,
    limit: int = 20,
    difficulty: Optional[str] = None,
) -> list[dict]:
    """Questions with the lowest pass rate — hardest in the employability track."""
    try:
        db = next(get_db())
        params: dict = {"limit": limit}
        college_clause = ""
        difficulty_clause = ""
        if college_name:
            college_clause = "AND c.name ILIKE :college"
            params["college"] = f"%{college_name}%"
        if difficulty:
            difficulty_clause = "AND ets.difficulty ILIKE :difficulty"
            params["difficulty"] = difficulty
        result = db.execute(text(f"""
            SELECT
                ets.question_id,
                MAX(ets.title)                                           AS title,
                MAX(ets.difficulty)                                      AS difficulty,
                MAX(d.domain)                                            AS domain,
                MAX(qsd.name)                                            AS sub_domain,
                COUNT(ets.id)                                            AS total_attempts,
                COUNT(DISTINCT ets.user_id)                              AS unique_students,
                COUNT(CASE WHEN ets.status = 'pass' THEN 1 END)         AS passed,
                ROUND(
                    COUNT(CASE WHEN ets.status = 'pass' THEN 1 END)*100.0
                    / NULLIF(COUNT(ets.id), 0), 2
                )                                                        AS pass_rate_percent
            FROM employability_track.employability_track_submission ets
            JOIN public.user               u   ON u.id  = ets.user_id
            JOIN public.college            c   ON c.id  = u.college_id
            LEFT JOIN public.domains       d   ON d.id  = ets.domain_id
            LEFT JOIN public.question_sub_domain qsd ON qsd.id = ets.sub_domain_id
            WHERE 1=1 {college_clause} {difficulty_clause}
            GROUP BY ets.question_id
            HAVING COUNT(ets.id) >= 5
            ORDER BY pass_rate_percent ASC, total_attempts DESC
            LIMIT :limit
        """), params).fetchall()
        return _rows_to_dicts(result)
    except Exception as e:
        logger.error(f"get_emp_hardest_questions error: {e}")
        return []


def get_emp_daily_trend(
    college_name: Optional[str] = None,
    days: int = 30,
) -> list[dict]:
    """Submission count per day over the last N days."""
    try:
        db = next(get_db())
        params: dict = {"since": date.today() - timedelta(days=days)}
        college_clause = ""
        if college_name:
            college_clause = "AND c.name ILIKE :college"
            params["college"] = f"%{college_name}%"
        result = db.execute(text(f"""
            SELECT
                ets.create_at::date                                      AS submission_date,
                COUNT(ets.id)                                            AS total_submissions,
                COUNT(DISTINCT ets.user_id)                              AS unique_students,
                COUNT(CASE WHEN ets.status = 'pass' THEN 1 END)         AS passed,
                ROUND(
                    COUNT(CASE WHEN ets.status = 'pass' THEN 1 END)*100.0
                    / NULLIF(COUNT(ets.id), 0), 2
                )                                                        AS pass_rate_percent
            FROM employability_track.employability_track_submission ets
            JOIN public.user    u ON u.id = ets.user_id
            JOIN public.college c ON c.id = u.college_id
            WHERE ets.create_at::date >= :since {college_clause}
            GROUP BY ets.create_at::date
            ORDER BY submission_date DESC
        """), params).fetchall()
        return _rows_to_dicts(result)
    except Exception as e:
        logger.error(f"get_emp_daily_trend error: {e}")
        return []


def get_emp_pass_rate(
    college_name: Optional[str] = None,
) -> list[dict]:
    """Overall employability pass rate per college."""
    try:
        db = next(get_db())
        params: dict = {}
        college_clause = ""
        if college_name:
            college_clause = "AND c.name ILIKE :college"
            params["college"] = f"%{college_name}%"
        result = db.execute(text(f"""
            SELECT
                c.name                                                   AS college,
                COUNT(ets.id)                                            AS total_submissions,
                COUNT(DISTINCT ets.user_id)                              AS unique_students,
                COUNT(CASE WHEN ets.status = 'pass' THEN 1 END)         AS total_passed,
                ROUND(
                    COUNT(CASE WHEN ets.status = 'pass' THEN 1 END)*100.0
                    / NULLIF(COUNT(ets.id), 0), 2
                )                                                        AS pass_rate_percent
            FROM employability_track.employability_track_submission ets
            JOIN public.user    u ON u.id = ets.user_id
            JOIN public.college c ON c.id = u.college_id
            WHERE 1=1 {college_clause}
            GROUP BY c.name
            ORDER BY pass_rate_percent DESC
        """), params).fetchall()
        return _rows_to_dicts(result)
    except Exception as e:
        logger.error(f"get_emp_pass_rate error: {e}")
        return []


def get_emp_user_profile(
    student_name: str,
    college_name: Optional[str] = None,
    difficulty: Optional[str] = None,
    language: Optional[str] = None,
    date_filter: Optional[str] = None,
) -> dict:
    """Full employability profile for a student — summary, submissions, question status breakdown."""
    try:
        db = next(get_db())
        base_params: dict = {"name": f"%{student_name}%"}
        college_clause = ""
        if college_name:
            college_clause = "AND c.name ILIKE :college"
            base_params["college"] = f"%{college_name}%"

        # ── Section 1: Submission history ──────────────────────────────────
        sub_params = dict(base_params)
        filters = ""
        if difficulty:
            filters += " AND ets.difficulty ILIKE :difficulty"
            sub_params["difficulty"] = difficulty
        if language:
            filters += " AND ets.language ILIKE :language"
            sub_params["language"] = f"%{language}%"
        if date_filter == "today":
            filters += " AND ets.create_at::date = CURRENT_DATE"
        elif date_filter:
            filters += f" AND ets.create_at::date = '{date_filter}'"

        submissions = db.execute(text(f"""
            SELECT
                d.domain        AS domain,
                qsd.name        AS sub_domain,
                ets.title,
                ets.difficulty,
                ets.language,
                ets.status,
                ets.obtained_score,
                ets.points      AS max_points,
                ets.create_at
            FROM employability_track.employability_track_submission ets
            JOIN public.user               u   ON u.id   = ets.user_id
            JOIN public.college            c   ON c.id   = u.college_id
            LEFT JOIN public.domains       d   ON d.id   = ets.domain_id
            LEFT JOIN public.question_sub_domain qsd ON qsd.id = ets.sub_domain_id
            WHERE (u.first_name || ' ' || u.last_name) ILIKE :name
              {college_clause} {filters}
            ORDER BY ets.create_at DESC
            LIMIT 50
        """), sub_params).fetchall()

        # ── Section 2: Performance summary ─────────────────────────────────
        summary = db.execute(text(f"""
            SELECT
                u.first_name || ' ' || u.last_name  AS name,
                c.name                              AS college,
                COUNT(ets.id)                       AS total_submissions,
                SUM(ets.obtained_score)             AS total_score,
                COUNT(CASE WHEN ets.status = 'pass' THEN 1 END) AS total_passed,
                COUNT(CASE WHEN ets.status = 'fail' THEN 1 END) AS total_failed,
                ROUND(
                    COUNT(CASE WHEN ets.status = 'pass' THEN 1 END)*100.0
                    / NULLIF(COUNT(ets.id), 0), 2
                )                                   AS pass_rate_percent,
                COUNT(DISTINCT ets.language)        AS languages_used
            FROM employability_track.employability_track_submission ets
            JOIN public.user    u ON u.id = ets.user_id
            JOIN public.college c ON c.id = u.college_id
            WHERE (u.first_name || ' ' || u.last_name) ILIKE :name {college_clause}
            GROUP BY u.id, u.first_name, u.last_name, c.name
        """), base_params).fetchall()

        # ── Section 3: Question status breakdown ───────────────────────────
        question_status = db.execute(text(f"""
            SELECT
                qs.status,
                COUNT(qs.question_id) AS question_count
            FROM employability_track.question_status qs
            JOIN public.user    u ON u.id = qs.user_id
            JOIN public.college c ON c.id = u.college_id
            WHERE (u.first_name || ' ' || u.last_name) ILIKE :name {college_clause}
            GROUP BY qs.status
        """), base_params).fetchall()

        return {
            "summary":         _rows_to_dicts(summary),
            "submissions":     _rows_to_dicts(submissions),
            "question_status": _rows_to_dicts(question_status),
        }

    except Exception as e:
        logger.error(f"get_emp_user_profile error: {e}")
        return {"summary": [], "submissions": [], "question_status": []}

# ══════════════════════════════════════════════════════════════════════════════
# ASSESS MODULE
# ══════════════════════════════════════════════════════════════════════════════

# Stop-words to strip from assessment title searches so "DSA test" → just "DSA"
_ASSESS_STOP_WORDS = {"test", "assessment", "the", "a", "an", "for", "in", "of"}


def _assess_title_clause(assessment_title: Optional[str], params: dict) -> str:
    """
    Build a WHERE clause that matches any meaningful keyword in assessment_title
    against the assessment_title column using ILIKE.
    e.g. "DSA test" → AND (a.assessment_title ILIKE '%DSA%')
         "angular"  → AND (a.assessment_title ILIKE '%angular%')
         "c assessment" → AND (a.assessment_title ILIKE '%c%')
    Returns empty string if assessment_title is None.
    """
    if not assessment_title:
        return ""
    keywords = [
        w for w in assessment_title.split()
        if w.lower() not in _ASSESS_STOP_WORDS
    ]
    if not keywords:
        # fallback — use full string if all words were stop-words
        params["assess_title_0"] = f"%{assessment_title}%"
        return "AND a.assessment_title ILIKE :assess_title_0"
    clauses = []
    for i, kw in enumerate(keywords):
        key = f"assess_kw_{i}"
        params[key] = f"%{kw}%"
        clauses.append(f"a.assessment_title ILIKE :{key}")
    return "AND (" + " OR ".join(clauses) + ")"


def get_assess_list(assessment_title: Optional[str] = None) -> list[dict]:
    """List all assessments with title, status, open/close time, shortlisted count, submitted count."""
    try:
        db = next(get_db())
        params: dict = {}
        title_clause = _assess_title_clause(assessment_title, params)
        result = db.execute(text(f"""
            SELECT
                a.id::text                               AS id,
                a.assessment_title                       AS title,
                a.status,
                a.assessment_type,
                a.open_time,
                a.close_time,
                a.round_number,
                jsonb_array_length(a.shortlisted_students)::int   AS shortlisted_count,
                jsonb_array_length(a.assessment_submitted_students)::int AS submitted_count,
                a.created_at
            FROM gest.assessment_shortlist a
            WHERE 1=1 {title_clause}
            ORDER BY a.created_at DESC
        """), params).fetchall()
        return _rows_to_dicts(result)
    except Exception as e:
        logger.error(f"get_assess_list error: {e}")
        return []


def get_assess_overview(assessment_title: Optional[str] = None) -> list[dict]:
    """Overview of a specific assessment — shortlisted, submitted, pass rate, avg score."""
    try:
        db = next(get_db())
        params: dict = {}
        title_clause = _assess_title_clause(assessment_title, params)
        result = db.execute(text(f"""
            SELECT
                a.assessment_title                          AS title,
                a.status,
                a.open_time,
                a.close_time,
                jsonb_array_length(a.shortlisted_students)::int      AS shortlisted_count,
                jsonb_array_length(a.assessment_submitted_students)::int AS submitted_count,
                COUNT(DISTINCT s.user_id)                   AS students_with_submissions,
                COUNT(s.id)                                 AS total_question_submissions,
                COUNT(CASE WHEN s.status = 'pass' THEN 1 END) AS total_passed,
                ROUND(
                    COUNT(CASE WHEN s.status = 'pass' THEN 1 END)*100.0
                    / NULLIF(COUNT(s.id), 0), 2
                )                                           AS pass_rate_percent,
                ROUND(AVG(s.obtained_score), 2)             AS avg_score
            FROM gest.assessment_shortlist a
            LEFT JOIN gest.assessment_final_attempt_submission s
                ON s.assessment_id = a.id::text
            WHERE 1=1 {title_clause}
            GROUP BY a.id, a.assessment_title, a.status, a.open_time,
                     a.close_time, a.shortlisted_students, a.assessment_submitted_students
            ORDER BY a.created_at DESC
        """), params).fetchall()
        return _rows_to_dicts(result)
    except Exception as e:
        logger.error(f"get_assess_overview error: {e}")
        return []


def get_assess_student_result(
    student_name: str,
    assessment_title: Optional[str] = None,
) -> list[dict]:
    """A student's per-question results across all or a specific assessment."""
    try:
        db = next(get_db())
        params: dict = {"name": f"%{student_name}%"}
        title_clause = _assess_title_clause(assessment_title, params)
        result = db.execute(text(f"""
            SELECT
                u.first_name || ' ' || u.last_name      AS student_name,
                a.assessment_title                      AS assessment,
                s.question_type,
                s.skill,
                s.difficulty,
                s.hackathon_sub_domain                  AS sub_domain,
                s.language,
                s.status,
                s.obtained_score,
                s.question_score,
                s.submission_time
            FROM gest.assessment_final_attempt_submission s
            JOIN public.user u ON u.id::text = s.user_id
            JOIN gest.assessment_shortlist a ON a.id::text = s.assessment_id
            WHERE (u.first_name || ' ' || u.last_name) ILIKE :name
              {title_clause}
            ORDER BY s.submission_time DESC
            LIMIT 50
        """), params).fetchall()
        return _rows_to_dicts(result)
    except Exception as e:
        logger.error(f"get_assess_student_result error: {e}")
        return []


def get_assess_top_scorers(
    assessment_title: Optional[str] = None,
    limit: int = 10,
) -> list[dict]:
    """Top N students by total score for a given assessment."""
    try:
        db = next(get_db())
        params: dict = {"limit": limit}
        title_clause = _assess_title_clause(assessment_title, params)

        # Primary: assessment_final_attempt_submission joined via assessment_id
        result = db.execute(text(f"""
            SELECT
                u.first_name || ' ' || u.last_name      AS name,
                u.email,
                a.assessment_title                      AS assessment,
                SUM(s.obtained_score)                   AS total_score,
                COUNT(CASE WHEN s.status = 'pass' THEN 1 END) AS questions_passed,
                COUNT(s.id)                             AS questions_attempted
            FROM gest.assessment_final_attempt_submission s
            JOIN public.user u ON u.id = s.user_id
            JOIN gest.assessment_shortlist a ON a.id::text = s.assessment_id
            WHERE 1=1 {title_clause}
            GROUP BY u.id, u.first_name, u.last_name, u.email, a.assessment_title
            ORDER BY total_score DESC
            LIMIT :limit
        """), params).fetchall()

        # Fallback: assessment_test_submission — join via round_id = hackathon_id
        if not result:
            result = db.execute(text(f"""
                SELECT
                    u.first_name || ' ' || u.last_name  AS name,
                    u.email,
                    a.assessment_title                  AS assessment,
                    SUM(s.score)                        AS total_score,
                    COUNT(CASE WHEN s.status = 'pass' THEN 1 END) AS questions_passed,
                    COUNT(s.id)                         AS questions_attempted
                FROM gest.assessment_test_submission s
                JOIN public.user u ON u.id::text = s.user_id
                JOIN gest.assessment_shortlist a ON a.hackathon_id = s.round_id
                WHERE 1=1 {title_clause}
                GROUP BY u.id, u.first_name, u.last_name, u.email, a.assessment_title
                ORDER BY total_score DESC
                LIMIT :limit
            """), params).fetchall()

        return _rows_to_dicts(result)
    except Exception as e:
        logger.error(f"get_assess_top_scorers error: {e}")
        return []


def get_assess_pass_rate(
    assessment_title: Optional[str] = None,
) -> list[dict]:
    """Pass rate per assessment, optionally filtered by title."""
    try:
        db = next(get_db())
        params: dict = {}
        title_clause = _assess_title_clause(assessment_title, params)
        result = db.execute(text(f"""
            SELECT
                a.assessment_title                      AS assessment,
                a.status,
                COUNT(s.id)                             AS total_submissions,
                COUNT(CASE WHEN s.status = 'pass' THEN 1 END) AS passed,
                COUNT(CASE WHEN s.status = 'fail' THEN 1 END) AS failed,
                ROUND(
                    COUNT(CASE WHEN s.status = 'pass' THEN 1 END)*100.0
                    / NULLIF(COUNT(s.id), 0), 2
                )                                       AS pass_rate_percent,
                ROUND(AVG(s.obtained_score), 2)         AS avg_score
            FROM gest.assessment_shortlist a
            LEFT JOIN gest.assessment_final_attempt_submission s
                ON s.assessment_id = a.id::text
            WHERE 1=1 {title_clause}
            GROUP BY a.id, a.assessment_title, a.status
            ORDER BY pass_rate_percent DESC
        """), params).fetchall()
        return _rows_to_dicts(result)
    except Exception as e:
        logger.error(f"get_assess_pass_rate error: {e}")
        return []


def get_assess_skill_breakdown(
    assessment_title: Optional[str] = None,
) -> list[dict]:
    """Pass rate grouped by skill/subdomain for an assessment."""
    try:
        db = next(get_db())
        params: dict = {}
        title_clause = _assess_title_clause(assessment_title, params)
        result = db.execute(text(f"""
            SELECT
                a.assessment_title                      AS assessment,
                s.skill,
                COUNT(s.id)                             AS total_submissions,
                COUNT(DISTINCT s.user_id)               AS unique_students,
                COUNT(CASE WHEN s.status = 'pass' THEN 1 END) AS passed,
                ROUND(
                    COUNT(CASE WHEN s.status = 'pass' THEN 1 END)*100.0
                    / NULLIF(COUNT(s.id), 0), 2
                )                                       AS pass_rate_percent,
                ROUND(AVG(s.obtained_score), 2)         AS avg_score
            FROM gest.assessment_final_attempt_submission s
            JOIN gest.assessment_shortlist a ON a.id::text = s.assessment_id
            WHERE s.skill IS NOT NULL {title_clause}
            GROUP BY a.assessment_title, s.skill
            ORDER BY total_submissions DESC
        """), params).fetchall()
        return _rows_to_dicts(result)
    except Exception as e:
        logger.error(f"get_assess_skill_breakdown error: {e}")
        return []


def get_assess_difficulty_breakdown(
    assessment_title: Optional[str] = None,
) -> list[dict]:
    """Pass rate split by difficulty (easy/medium/hard) for an assessment."""
    try:
        db = next(get_db())
        params: dict = {}
        title_clause = _assess_title_clause(assessment_title, params)
        result = db.execute(text(f"""
            SELECT
                a.assessment_title                      AS assessment,
                s.difficulty,
                COUNT(s.id)                             AS total_submissions,
                COUNT(DISTINCT s.user_id)               AS unique_students,
                COUNT(CASE WHEN s.status = 'pass' THEN 1 END) AS passed,
                ROUND(
                    COUNT(CASE WHEN s.status = 'pass' THEN 1 END)*100.0
                    / NULLIF(COUNT(s.id), 0), 2
                )                                       AS pass_rate_percent
            FROM gest.assessment_final_attempt_submission s
            JOIN gest.assessment_shortlist a ON a.id::text = s.assessment_id
            WHERE s.difficulty IS NOT NULL {title_clause}
            GROUP BY a.assessment_title, s.difficulty
            ORDER BY a.assessment_title,
                     CASE s.difficulty WHEN 'easy' THEN 1 WHEN 'medium' THEN 2 WHEN 'hard' THEN 3 ELSE 4 END
        """), params).fetchall()

        # fallback using assessment_test_submission
        if not result:
            result = db.execute(text(f"""
                SELECT
                    a.assessment_title                      AS assessment,
                    'all' AS difficulty,
                    COUNT(s.id)                             AS total_submissions,
                    COUNT(DISTINCT s.user_id)               AS unique_students,
                    COUNT(CASE WHEN s.status = 'pass' THEN 1 END) AS passed,
                    ROUND(
                        COUNT(CASE WHEN s.status = 'pass' THEN 1 END)*100.0
                        / NULLIF(COUNT(s.id), 0), 2
                    )                                       AS pass_rate_percent
                FROM gest.assessment_test_submission s
                JOIN public.user u ON u.id::text = s.user_id
                JOIN gest.assessment_shortlist a
                    ON a.hackathon_id = s.round_id
                WHERE 1=1 {title_clause}
                GROUP BY a.assessment_title
            """), params).fetchall()

        return _rows_to_dicts(result)
    except Exception as e:
        logger.error(f"get_assess_difficulty_breakdown error: {e}")
        return []


def get_assess_completion_rate(
    assessment_title: Optional[str] = None,
) -> list[dict]:
    """How many shortlisted students completed vs started vs didn't attempt."""
    try:
        db = next(get_db())
        params: dict = {}
        title_clause = _assess_title_clause(assessment_title, params)
        result = db.execute(text(f"""
            SELECT
                a.assessment_title                              AS assessment,
                a.status,
                jsonb_array_length(a.shortlisted_students)::int              AS shortlisted_count,
                jsonb_array_length(a.assessment_submitted_students)::int AS submitted_count,
                COUNT(DISTINCT CASE WHEN r.status = 'completed' THEN r.user_id END) AS completed,
                COUNT(DISTINCT CASE WHEN r.status = 'started'   THEN r.user_id END) AS in_progress,
                ROUND(
                    jsonb_array_length(a.assessment_submitted_students)::int*100.0
                    / NULLIF(jsonb_array_length(a.shortlisted_students)::int, 0), 2
                )                                               AS completion_rate_percent
            FROM gest.assessment_shortlist a
            LEFT JOIN gest.assessment_round_attempt_history r
                ON r.assessment_id = a.id
            WHERE 1=1 {title_clause}
            GROUP BY a.id, a.assessment_title, a.status,
                     a.shortlisted_students, a.assessment_submitted_students
            ORDER BY a.created_at DESC
        """), params).fetchall()
        return _rows_to_dicts(result)
    except Exception as e:
        logger.error(f"get_assess_completion_rate error: {e}")
        return []


def get_assess_recent(limit: int = 10) -> list[dict]:
    """Most recently created or active assessments."""
    try:
        db = next(get_db())
        result = db.execute(text("""
            SELECT
                a.assessment_title                          AS title,
                a.status,
                a.assessment_type,
                a.open_time,
                a.close_time,
                jsonb_array_length(a.shortlisted_students)::int      AS shortlisted_count,
                jsonb_array_length(a.assessment_submitted_students)::int AS submitted_count,
                a.created_at
            FROM gest.assessment_shortlist a
            ORDER BY a.created_at DESC
            LIMIT :limit
        """), {"limit": limit}).fetchall()
        return _rows_to_dicts(result)
    except Exception as e:
        logger.error(f"get_assess_recent error: {e}")
        return []


def get_assess_student_attempts(
    student_name: str,
) -> list[dict]:
    """Attempt history for a student across all assessments — status, time taken, score."""
    try:
        db = next(get_db())
        result = db.execute(text("""
            SELECT
                u.first_name || ' ' || u.last_name      AS student_name,
                a.assessment_title                      AS assessment,
                r.status,
                r.started_at,
                r.submitted_at,
                ROUND(
                    EXTRACT(EPOCH FROM (r.submitted_at - r.started_at)) / 60.0, 1
                )                                       AS duration_minutes,
                SUM(s.obtained_score)                   AS total_score
            FROM gest.assessment_round_attempt_history r
            JOIN public.user u ON u.id::text = r.user_id
            JOIN gest.assessment_shortlist a ON a.id = r.assessment_id
            LEFT JOIN gest.assessment_final_attempt_submission s
                ON s.user_id = r.user_id AND s.assessment_id = a.id::text
            WHERE (u.first_name || ' ' || u.last_name) ILIKE :name
            GROUP BY u.id, u.first_name, u.last_name,
                     a.assessment_title, r.status, r.started_at, r.submitted_at
            ORDER BY r.started_at DESC
        """), {"name": f"%{student_name}%"}).fetchall()

        # fallback — try assessment_test_submission if no round attempt history
        if not result:
            result = db.execute(text("""
                SELECT
                    u.first_name || ' ' || u.last_name  AS student_name,
                    'assessment_test_submission'         AS assessment,
                    s.status,
                    s.start_time                        AS started_at,
                    s.end_time                          AS submitted_at,
                    s.time_taken,
                    s.score                             AS total_score
                FROM gest.assessment_test_submission s
                JOIN public.user u ON u.id::text = s.user_id
                WHERE (u.first_name || ' ' || u.last_name) ILIKE :name
                ORDER BY s.start_time DESC
            """), {"name": f"%{student_name}%"}).fetchall()

        return _rows_to_dicts(result)
    except Exception as e:
        logger.error(f"get_assess_student_attempts error: {e}")
        return []