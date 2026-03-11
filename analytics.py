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


def get_top_scorers(college_name: Optional[str] = None, limit: int = 10) -> list[dict]:
    try:
        db = next(get_db())
        params = {"limit": limit}
        college_clause = ""
        if college_name:
            college_clause = "AND c.name ILIKE :college"
            params["college"] = f"%{college_name}%"
        result = db.execute(text(f"""
            SELECT u.first_name || ' ' || u.last_name AS name, c.name AS college,
                   SUM(ps.obtained_score) AS total_score,
                   COUNT(DISTINCT ps.question_id) AS questions_attempted
            FROM pod.pod_submission ps
            JOIN public.user u ON u.id = ps.user_id
            JOIN public.college c ON c.id = u.college_id
            WHERE u.role = 'Student' {college_clause}
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