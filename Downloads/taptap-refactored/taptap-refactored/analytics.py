# analytics.py — TapTap Analytics Chatbot
# Three broad dispatcher functions replace 44 narrow ones.
# Each reads params["query_type"] and executes the matching SQL.
# All SQL is identical to the original narrow functions — purely structural refactor.

from datetime import date, timedelta
from typing import Any, Optional, Union
from sqlalchemy import text
from db import get_db
from logger import logger
from constants import (
    QT_POD_WHO_SOLVED_TODAY, QT_POD_ATTEMPT_COUNT_TODAY, QT_POD_QUESTION_TODAY,
    QT_POD_FASTEST_SOLVER, QT_POD_NOT_ATTEMPTED_TODAY, QT_POD_PASS_FAIL_SUMMARY,
    QT_POD_PASS_RATE, QT_POD_TOP_PASSERS, QT_POD_NEVER_PASSED, QT_POD_WEEKLY_PASSERS,
    QT_POD_DIFFICULTY_BREAKDOWN, QT_POD_LANGUAGE_BREAKDOWN, QT_POD_HARD_SOLVERS,
    QT_POD_LONGEST_STREAK, QT_POD_ACTIVE_STREAKS, QT_POD_LOST_STREAK,
    QT_POD_TOP_COINS, QT_POD_TOTAL_POINTS_TODAY, QT_POD_TOP_SCORERS,
    QT_POD_BADGE_EARNERS, QT_POD_WEEKLY_BADGE_EARNERS, QT_POD_DAILY_TREND, QT_POD_STUDENT_PROFILE,
    QT_EMP_TOP_SCORERS, QT_EMP_DIFFICULTY_STATS, QT_EMP_LANGUAGE_STATS,
    QT_EMP_DOMAIN_BREAKDOWN, QT_EMP_SUBDOMAIN_BREAKDOWN, QT_EMP_QUESTION_TYPE_STATS,
    QT_EMP_MOST_SOLVED, QT_EMP_RECENT_ACTIVITY, QT_EMP_HARDEST_QUESTIONS,
    QT_EMP_DAILY_TREND, QT_EMP_PASS_RATE, QT_EMP_DOMAIN_STUDENTS, QT_EMP_USER_PROFILE,
    QT_ASSESS_LIST, QT_ASSESS_OVERVIEW, QT_ASSESS_STUDENT_RESULT,
    QT_ASSESS_TOP_SCORERS, QT_ASSESS_PASS_RATE, QT_ASSESS_SKILL_BREAKDOWN,
    QT_ASSESS_DIFFICULTY_BREAKDOWN, QT_ASSESS_COMPLETION_RATE,
    QT_ASSESS_RECENT, QT_ASSESS_STUDENT_ATTEMPTS,
    QT_ASSESS_SHORTLISTED_NOT_SUBMITTED, QT_ASSESS_PASSED_STUDENTS,
)

# ══════════════════════════════════════════════════════════════════════════════
# COLLEGE NAME NORMALIZATION
# Maps common aliases/abbreviations faculty type → keyword used in ILIKE filter
# e.g. "CMRIT" → "CMR" matches "CMR Technical Campus", "CMR Institute Of Technology" etc.
# ══════════════════════════════════════════════════════════════════════════════

_COLLEGE_ALIASES: dict[str, str] = {
    # ── CMR group ─────────────────────────────────────────────────────────────
    "cmrit":                        "CMR",
    "cmr institute":                "CMR",
    "cmr technical":                "CMR",
    "cmr engineering":              "CMR",
    "cmr college":                  "CMR",
    "cmr university":               "CMR",
    # ── Geethanjali ───────────────────────────────────────────────────────────
    "geethanjali":                  "Geethanjali",
    "gcet":                         "Geethanjali",
    # ── DVR & MIC ─────────────────────────────────────────────────────────────
    "dvr":                          "DVR",
    "mic college":                  "DVR",
    "dvr mic":                      "DVR",
    "kanchikacherla":               "DVR",
    # ── Annamacharya ──────────────────────────────────────────────────────────
    "annamacharya":                 "Annamacharya",
    "aits":                         "Annamacharya",
    # ── Srinivasa (Amalapuram) ────────────────────────────────────────────────
    "srinivasa institute":          "Srinivasa Institute Of Engineering",
    "siet":                         "Srinivasa Institute Of Engineering",
    # ── MVSR ──────────────────────────────────────────────────────────────────
    "mvsr":                         "MVSR",
    # ── VIT ───────────────────────────────────────────────────────────────────
    "vit":                          "Vellore Institute Of Technology",
    "vit vellore":                  "Vellore Institute Of Technology",
    "vit chennai":                  "Vellore Institute Of Technology, Chennai",
    "vit ap":                       "VIT-AP",
    "vit bhopal":                   "VIT Bhopal",
    # ── SRM ───────────────────────────────────────────────────────────────────
    "srm":                          "SRM",
    "srm university":               "SRM",
    "srm institute":                "SRM",
    "srm chennai":                  "Srm Institute Of Science And Technology",
    "srm ap":                       "SRM University AP",
    # ── Anna University ───────────────────────────────────────────────────────
    "anna university":              "Anna University",
    "au chennai":                   "Anna University",
    "ceg":                          "University Departments Of Anna University, Chennai - Ceg Campus",
    "mit anna":                     "Anna University - MIT",
    # ── NIT ───────────────────────────────────────────────────────────────────
    "nit warangal":                 "NIT Warangal",
    "nit trichy":                   "NIT Trichy",
    "nit":                          "NIT",
    # ── IIT ───────────────────────────────────────────────────────────────────
    "iit hyderabad":                "Indian Institute of Technology Hyderabad",
    "iith":                         "Indian Institute of Technology Hyderabad",
    "iit tirupati":                 "IIT Tirupati",
    "iit madras":                   "Indian Institute of Technology Madras",
    "iitm":                         "Indian Institute of Technology Madras",
    # ── Vardhaman ─────────────────────────────────────────────────────────────
    "vardhaman":                    "Vardhaman",
    "vcew":                         "Vardhaman",
    # ── Vasavi ────────────────────────────────────────────────────────────────
    "vasavi":                       "Vasavi",
    "vce":                          "Vasavi College Of Engineering",
    # ── Osmania ───────────────────────────────────────────────────────────────
    "osmania":                      "Osmania",
    "ou":                           "Osmania University",
    # ── Sreenidhi ─────────────────────────────────────────────────────────────
    "sreenidhi":                    "Sreenidhi",
    "snist":                        "Sreenidhi",
    # ── Muffakham Jah ─────────────────────────────────────────────────────────
    "mjcet":                        "Muffakham Jah",
    "muffakham":                    "Muffakham Jah",
    # ── Stanley ───────────────────────────────────────────────────────────────
    "stanley":                      "Stanley",
    # ── Raghu ─────────────────────────────────────────────────────────────────
    "raghu":                        "Raghu",
    # ── Narayana ──────────────────────────────────────────────────────────────
    "narayana engineering":         "Narayana Engineering",
    # ── Vignan ────────────────────────────────────────────────────────────────
    "vignan":                       "Vignan",
    "vfstr":                        "Vignan",
    # ── Pallavi ───────────────────────────────────────────────────────────────
    "pallavi":                      "Pallavi",
    # ── MLR ───────────────────────────────────────────────────────────────────
    "mlr":                          "Mlr Institute",
    "mlrit":                        "Mlr Institute",
    # ── ACE ───────────────────────────────────────────────────────────────────
    "ace":                          "ACE Engineering College",
    # ── CVR ───────────────────────────────────────────────────────────────────
    "cvr":                          "Cvr College Of Engineering",
    # ── BVRIT ─────────────────────────────────────────────────────────────────
    "bvrit":                        "Bvrit Hyderabad",
    # ── CBIT ──────────────────────────────────────────────────────────────────
    "cbit":                         "Chaitanya Bharathi Institute",
    # ── JNTU ──────────────────────────────────────────────────────────────────
    "jntu hyderabad":               "Jntu College Of Engineering, Hyderabad",
    "jntu kakinada":                "Jntu College Of Engineering, Kakinada",
    "jntu anantapur":               "Jntu College Of Engineering Anantapur",
    "jntuh":                        "Jntu College Of Engineering, Hyderabad",
    "jntuk":                        "Jntu College Of Engineering, Kakinada",
    "jntua":                        "Jntu College Of Engineering Anantapur",
    # ── RGUKT ─────────────────────────────────────────────────────────────────
    "rgukt":                        "RGUKT",
    "iiit rgukt":                   "RGUKT",
    # ── KL University ─────────────────────────────────────────────────────────
    "kl university":                "Koneru Lakshmaiah University",
    "klu":                          "Koneru Lakshmaiah University",
    "klef":                         "koneru Lakshmaiah Education Foundation",
    # ── Aditya ────────────────────────────────────────────────────────────────
    "aditya":                       "Aditya",
    # ── Anurag ────────────────────────────────────────────────────────────────
    "anurag":                       "Anurag",
    # ── Aurora ────────────────────────────────────────────────────────────────
    "aurora":                       "Aurora",
    # ── Avanthi ───────────────────────────────────────────────────────────────
    "avanthi":                      "Avanthi",
    # ── Malla Reddy ───────────────────────────────────────────────────────────
    "malla reddy":                  "Malla Reddy",
    "mrec":                         "Malla Reddy Engineering College",
    "mrcet":                        "Malla Reddy College Of Engineering",
    "mrits":                        "Malla Reddy Institute",
    # ── Marri Laxman Reddy ────────────────────────────────────────────────────
    "mlritm":                       "Marri Laxman Reddy",
    "marri laxman":                 "Marri Laxman Reddy",
    # ── Sreyas ────────────────────────────────────────────────────────────────
    "sreyas":                       "Sreyas",
    # ── Bapatla ───────────────────────────────────────────────────────────────
    "bapatla":                      "Bapatla",
    "bec":                          "Bapatla Engineering College",
    # ── Amrita ────────────────────────────────────────────────────────────────
    "amrita":                       "Amrita",
    # ── G Narayanamma ─────────────────────────────────────────────────────────
    "gnits":                        "G. Narayanamma Institute",
    "g narayanamma":                "G. Narayanamma Institute",
    # ── Sreenidhi / SNIST ─────────────────────────────────────────────────────
    "sreenidhi institute":          "Sreenidhi Institute Of Science And Technology",
    # ── Vignana Bharathi ──────────────────────────────────────────────────────
    "vbit":                         "Vignana Bharathi Institute Of Technology",
    "vbec":                         "Vignana Bharathi Engineering College",
    # ── Sri Chaitanya ─────────────────────────────────────────────────────────
    "sri chaitanya":                "Sri Chaitanya",
    # ── Nalla Malla Reddy ─────────────────────────────────────────────────────
    "nmrec":                        "Nalla Malla Reddy Engineering College",
    "nalla malla reddy":            "Nalla Malla Reddy",
    # ── RISE ──────────────────────────────────────────────────────────────────
    "rise":                         "Rise Krishna Sai",
}


def _normalize_college(college_name: str) -> str:
    """
    Normalize a college name typed by faculty to the best ILIKE keyword.
    Tries exact alias match first, then returns the original trimmed value.
    """
    if not college_name:
        return college_name
    key = college_name.strip().lower()
    return _COLLEGE_ALIASES.get(key, college_name.strip())


def _rows_to_dicts(rows) -> list[dict]:
    return [dict(r._mapping) for r in rows]


# ══════════════════════════════════════════════════════════════════════════════
# DOMAIN NAME NORMALIZATION
# Maps common abbreviations/aliases faculty type → keyword used in ILIKE filter
# ══════════════════════════════════════════════════════════════════════════════

_DOMAIN_ALIASES: dict[str, str] = {
    # Data Structures
    "dsa":                      "Data Structures",
    "data structures":          "Data Structures",
    "ds":                       "Data Structures",
    # Algorithms
    "algo":                     "Algorithms",
    "algorithms":               "Algorithms",
    # Dynamic Programming
    "dp":                       "Dynamic Programming",
    "dynamic programming":      "Dynamic Programming",
    # Database
    "dbms":                     "dbms",
    "database":                 "dbms",
    "db":                       "dbms",
    "sql":                      "SQL",
    "mysql":                    "MySQL",
    "mongodb":                  "mongodb",
    "mongo":                    "mongodb",
    # Programming languages
    "python":                   "Python",
    "java":                     "Java",
    "javascript":               "javascript",
    "js":                       "javascript",
    "c programming":            "C Programming",
    "c lang":                   "c language",
    "c++":                      "c++ programming",
    "cpp":                      "c++ programming",
    "php":                      "php",
    "r lang":                   "r language",
    ".net":                     ".NET",
    "dotnet":                   ".NET",
    # Web / Full Stack
    "full stack":               "Full Stack Development",
    "fullstack":                "Full Stack Development",
    "mern":                     "MERN",
    "react":                    "react js",
    "angular":                  "angular skill test",
    "django":                   "django",
    "nodejs":                   "nodejs",
    "node":                     "nodejs",
    "spring boot":              "spring boot",
    "springboot":               "Springboot",
    "html":                     "html",
    "css":                      "css",
    # Cloud / DevOps
    "aws":                      "aws",
    "cloud":                    "Cloud Computing",
    "cloud computing":          "Cloud Computing",
    # Data Science / ML / AI
    "data science":             "Data Science",
    "ml":                       "Machine Learning",
    "machine learning":         "Machine Learning",
    "deep learning":            "Deep Learning",
    "ai":                       "AIMLDS",
    "numpy":                    "Numpy",
    "pandas":                   "Pandas",
    # Aptitude / Quantitative
    "aptitude":                 "Aptitude",
    "quant":                    "Quantitative Aptitude",
    "quantitative":             "Quantitative Aptitude",
    "logical":                  "logical ability",
    "verbal":                   "verbal ability",
    "english":                  "English",
    # Computer Science fundamentals
    "os":                       "computer science",
    "cn":                       "networking",
    "networking":               "networking",
    "cyber security":           "Cyber Security",
    "cybersecurity":            "Cyber Security",
    "security":                 "Security",
    # Placement / Interview
    "placement":                "Placement Preparation",
    "interview":                "Interview Preparation",
    "interview prep":           "Interview Preparation",
    "hr":                       "Human Resource",
    # Mathematics / Statistics
    "maths":                    "Mathematics",
    "math":                     "Mathematics",
    "statistics":               "Statistics",
    # Other
    "coding":                   "Coding",
    "general knowledge":        "general knowledge",
    "gk":                       "general knowledge",
}



def _normalize_domain(domain_name: str) -> str:
    """
    Normalize a domain name typed by faculty to the best ILIKE keyword.
    Tries exact alias match first (case-insensitive), then returns original.
    """
    if not domain_name:
        return domain_name
    key = domain_name.strip().lower()
    return _DOMAIN_ALIASES.get(key, domain_name.strip())


# ══════════════════════════════════════════════════════════════════════════════
# ASSESS HELPER — unchanged from original
# ══════════════════════════════════════════════════════════════════════════════

_ASSESS_STOP_WORDS = {"test", "assessment", "the", "a", "an", "for", "in", "of"}


def _assess_title_clause(assessment_title: Optional[str], params: dict) -> str:
    """
    Build a WHERE clause for assessment title filtering.
    - If the title looks exact (contains ' - ' or > 25 chars), use a single ILIKE match.
    - Otherwise split into keywords and OR them together, stripping stop-words.
    """
    if not assessment_title:
        return ""

    if " - " in assessment_title or len(assessment_title) > 25:
        params["assess_title_exact"] = f"%{assessment_title}%"
        return "AND a.assessment_title ILIKE :assess_title_exact"

    keywords = [
        w for w in assessment_title.split()
        if w.lower() not in _ASSESS_STOP_WORDS
    ]
    if not keywords:
        params["assess_title_0"] = f"%{assessment_title}%"
        return "AND a.assessment_title ILIKE :assess_title_0"
    clauses = []
    for i, kw in enumerate(keywords):
        key = f"assess_kw_{i}"
        params[key] = f"%{kw}%"
        clauses.append(f"a.assessment_title ILIKE :{key}")
    return "AND (" + " OR ".join(clauses) + ")"


# ══════════════════════════════════════════════════════════════════════════════
# POD DISPATCHER
# ══════════════════════════════════════════════════════════════════════════════

def get_pod_data(params: dict) -> Union[list[dict], dict]:
    """
    Single entry point for all POD queries.
    params must include 'query_type' — one of the QT_POD_* constants.
    All other params are forwarded as-is to the matching SQL block.
    """
    qt             = params.get("query_type", "")
    college_name   = _normalize_college(params.get("college_name"))
    limit          = params.get("limit", 10)
    date_filter    = params.get("date_filter")
    week_filter    = params.get("week_filter")
    days           = params.get("days")
    min_streak     = params.get("min_streak", 3)
    student_name   = params.get("student_name", "")
    pod_type       = params.get("pod_type")
    language       = params.get("language")
    info_type      = params.get("info_type", "all")

    try:
        db = next(get_db())

        # ── Who solved today ──────────────────────────────────────────────────
        if qt == QT_POD_WHO_SOLVED_TODAY:
            p = {"today": date.today()}
            cc = ""
            bc = ""
            if college_name:
                cc = "AND c.name ILIKE :college"
                p["college"] = f"%{college_name}%"
            rows = db.execute(text(f"""
                SELECT u.first_name || ' ' || u.last_name AS name, u.email,
                       c.name AS college, ps.title, ps.difficulty,
                       ps.language, ps.obtained_score, ps.create_at
                FROM pod.pod_submission ps
                JOIN public.user u ON u.id = ps.user_id
                JOIN public.college c ON c.id = u.college_id
                WHERE ps.status = 'pass' AND ps.create_at::date = :today {cc}
                ORDER BY ps.create_at DESC
            """), p).fetchall()
            return _rows_to_dicts(rows)

        # ── Attempt count today ───────────────────────────────────────────────
        if qt == QT_POD_ATTEMPT_COUNT_TODAY:
            p = {"today": date.today()}
            cc = ""
            bc = ""
            if college_name:
                cc = "AND c.name ILIKE :college"
                p["college"] = f"%{college_name}%"
            rows = db.execute(text(f"""
                SELECT COUNT(DISTINCT pa.user_id) AS total_attempts,
                       COUNT(DISTINCT CASE WHEN ps.status='pass' THEN ps.user_id END) AS passed,
                       COUNT(DISTINCT CASE WHEN ps.status='fail' THEN ps.user_id END) AS failed
                FROM pod.pod_attempt pa
                JOIN public.user u ON u.id = pa.user_id
                JOIN public.college c ON c.id = u.college_id
                LEFT JOIN pod.pod_submission ps
                    ON ps.user_id = pa.user_id
                    AND ps.problem_of_the_day_id = pa.problem_of_the_day_id
                WHERE pa.create_at::date = :today {cc}
            """), p).fetchall()
            return _rows_to_dicts(rows)

        # ── Question today ────────────────────────────────────────────────────
        if qt == QT_POD_QUESTION_TODAY:
            rows = db.execute(text("""
                SELECT id, date, difficulty, type, unique_user_attempts, is_active
                FROM pod.problem_of_the_day
                WHERE date = (SELECT MAX(date) FROM pod.problem_of_the_day)
            """)).fetchall()
            return _rows_to_dicts(rows)

        # ── Fastest solver ────────────────────────────────────────────────────
        if qt == QT_POD_FASTEST_SOLVER:
            p = {"today": date.today(), "limit": limit}
            cc = ""
            bc = ""
            if college_name:
                cc = "AND c.name ILIKE :college"
                p["college"] = f"%{college_name}%"
            rows = db.execute(text(f"""
                SELECT u.first_name || ' ' || u.last_name AS name,
                       c.name AS college, ROUND(pa.time_taken / 1000.0, 1) AS time_taken_seconds,
                       pa.pod_started_at, pa.end_date
                FROM pod.pod_attempt pa
                JOIN public.user u ON u.id = pa.user_id
                JOIN public.college c ON c.id = u.college_id
                WHERE pa.create_at::date = :today AND pa.status = 'completed'
                  AND pa.time_taken IS NOT NULL {cc}
                ORDER BY pa.time_taken ASC LIMIT :limit
            """), p).fetchall()
            return _rows_to_dicts(rows)

        # ── Not attempted today ───────────────────────────────────────────────
        if qt == QT_POD_NOT_ATTEMPTED_TODAY:
            p = {"today": date.today(), "limit": limit}
            cc = ""
            bc = ""
            if college_name:
                cc = "AND c.name ILIKE :college"
                p["college"] = f"%{college_name}%"
            rows = db.execute(text(f"""
                SELECT u.first_name || ' ' || u.last_name AS name, u.email, c.name AS college
                FROM public.user u
                JOIN public.college c ON c.id = u.college_id
                WHERE u.role = 'Student' {cc}
                  AND u.id NOT IN (SELECT user_id FROM pod.pod_attempt WHERE create_at::date = :today)
                ORDER BY u.first_name LIMIT :limit
            """), p).fetchall()
            return _rows_to_dicts(rows)

        # ── Pass/fail summary ─────────────────────────────────────────────────
        if qt == QT_POD_PASS_FAIL_SUMMARY:
            p = {"limit": limit}
            dc = ""
            if date_filter == "today":
                dc = "AND ps.create_at::date = CURRENT_DATE"
            elif date_filter:
                dc = f"AND ps.create_at::date = '{date_filter}'"
            cc = ""
            bc = ""
            if college_name:
                cc = "AND c.name ILIKE :college"
                p["college"] = f"%{college_name}%"
            rows = db.execute(text(f"""
                SELECT u.first_name || ' ' || u.last_name AS name, c.name AS college,
                       COUNT(DISTINCT CASE WHEN ps.status='pass' THEN ps.question_id END) AS pass_count,
                       COUNT(DISTINCT CASE WHEN ps.status='fail' THEN ps.question_id END) AS fail_count,
                       COUNT(DISTINCT ps.question_id) AS total_questions
                FROM pod.pod_submission ps
                JOIN public.user u ON u.id = ps.user_id
                JOIN public.college c ON c.id = u.college_id
                WHERE u.role = 'Student' {dc} {cc}
                GROUP BY u.id, u.first_name, u.last_name, c.name
                ORDER BY pass_count DESC LIMIT :limit
            """), p).fetchall()
            return _rows_to_dicts(rows)

        # ── Pass rate ─────────────────────────────────────────────────────────
        if qt == QT_POD_PASS_RATE:
            p = {}
            cc = ""
            bc = ""
            if college_name:
                cc = "AND c.name ILIKE :college"
                p["college"] = f"%{college_name}%"
            rows = db.execute(text(f"""
                SELECT c.name AS college,
                       COUNT(DISTINCT CASE WHEN ps.status='pass' THEN ps.id END) AS total_passes,
                       COUNT(DISTINCT ps.id) AS total_submissions,
                       ROUND(COUNT(DISTINCT CASE WHEN ps.status='pass' THEN ps.id END)*100.0
                             / NULLIF(COUNT(DISTINCT ps.id),0), 2) AS pass_rate_percent
                FROM pod.pod_submission ps
                JOIN public.user u ON u.id = ps.user_id
                JOIN public.college c ON c.id = u.college_id
                WHERE u.role = 'Student' {cc}
                GROUP BY c.name ORDER BY c.name
            """), p).fetchall()
            return _rows_to_dicts(rows)

        # ── Top passers ───────────────────────────────────────────────────────
        if qt == QT_POD_TOP_PASSERS:
            p = {"limit": limit}
            cc = ""
            bc = ""
            if college_name:
                cc = "AND c.name ILIKE :college"
                p["college"] = f"%{college_name}%"
            rows = db.execute(text(f"""
                SELECT u.first_name || ' ' || u.last_name AS name, c.name AS college,
                       COUNT(DISTINCT ps.question_id) AS questions_passed,
                       SUM(ps.obtained_score) AS total_score
                FROM pod.pod_submission ps
                JOIN public.user u ON u.id = ps.user_id
                JOIN public.college c ON c.id = u.college_id
                WHERE ps.status = 'pass' AND u.role = 'Student' {cc}
                GROUP BY u.id, u.first_name, u.last_name, c.name
                ORDER BY questions_passed DESC LIMIT :limit
            """), p).fetchall()
            return _rows_to_dicts(rows)

        # ── Never passed ──────────────────────────────────────────────────────
        if qt == QT_POD_NEVER_PASSED:
            p = {"limit": limit}
            cc = ""
            bc = ""
            if college_name:
                cc = "AND c.name ILIKE :college"
                p["college"] = f"%{college_name}%"
            rows = db.execute(text(f"""
                SELECT u.first_name || ' ' || u.last_name AS name, u.email, c.name AS college
                FROM public.user u
                JOIN public.college c ON c.id = u.college_id
                WHERE u.role = 'Student' {cc}
                  AND u.id IN (SELECT DISTINCT user_id FROM pod.pod_submission)
                  AND u.id NOT IN (SELECT DISTINCT user_id FROM pod.pod_submission WHERE status='pass')
                ORDER BY u.first_name LIMIT :limit
            """), p).fetchall()
            return _rows_to_dicts(rows)

        # ── Weekly passers ────────────────────────────────────────────────────
        if qt == QT_POD_WEEKLY_PASSERS:
            week_start = date.today() - timedelta(days=date.today().weekday())
            p = {"week_start": week_start, "limit": limit}
            cc = ""
            bc = ""
            if college_name:
                cc = "AND c.name ILIKE :college"
                p["college"] = f"%{college_name}%"
            rows = db.execute(text(f"""
                SELECT u.first_name || ' ' || u.last_name AS name, c.name AS college,
                       COUNT(DISTINCT ps.question_id) AS questions_passed_this_week
                FROM pod.pod_submission ps
                JOIN public.user u ON u.id = ps.user_id
                JOIN public.college c ON c.id = u.college_id
                WHERE ps.status = 'pass' AND ps.create_at::date >= :week_start
                  AND u.role = 'Student' {cc}
                GROUP BY u.id, u.first_name, u.last_name, c.name
                ORDER BY questions_passed_this_week DESC LIMIT :limit
            """), p).fetchall()
            return _rows_to_dicts(rows)

        # ── Difficulty breakdown ──────────────────────────────────────────────
        if qt == QT_POD_DIFFICULTY_BREAKDOWN:
            p = {}
            cc = ""
            bc = ""
            if college_name:
                cc = "AND c.name ILIKE :college"
                p["college"] = f"%{college_name}%"
            rows = db.execute(text(f"""
                SELECT ps.difficulty,
                       COUNT(DISTINCT ps.user_id) AS students_attempted,
                       COUNT(DISTINCT CASE WHEN ps.status='pass' THEN ps.user_id END) AS students_passed,
                       ROUND(COUNT(DISTINCT CASE WHEN ps.status='pass' THEN ps.user_id END)*100.0
                             / NULLIF(COUNT(DISTINCT ps.user_id),0), 2) AS pass_rate_percent
                FROM pod.pod_submission ps
                JOIN public.user u ON u.id = ps.user_id
                JOIN public.college c ON c.id = u.college_id
                WHERE ps.difficulty IS NOT NULL AND u.role = 'Student' {cc}
                GROUP BY ps.difficulty ORDER BY ps.difficulty
            """), p).fetchall()
            return _rows_to_dicts(rows)

        # ── Language breakdown ────────────────────────────────────────────────
        if qt == QT_POD_LANGUAGE_BREAKDOWN:
            p = {}
            cc = ""
            bc = ""
            if college_name:
                cc = "AND c.name ILIKE :college"
                p["college"] = f"%{college_name}%"
            rows = db.execute(text(f"""
                SELECT ps.language,
                       COUNT(DISTINCT ps.user_id) AS students,
                       COUNT(ps.id) AS total_submissions,
                       COUNT(CASE WHEN ps.status='pass' THEN 1 END) AS passes
                FROM pod.pod_submission ps
                JOIN public.user u ON u.id = ps.user_id
                JOIN public.college c ON c.id = u.college_id
                WHERE ps.language IS NOT NULL AND u.role = 'Student' {cc}
                GROUP BY ps.language ORDER BY students DESC
            """), p).fetchall()
            return _rows_to_dicts(rows)

        # ── Hard solvers ──────────────────────────────────────────────────────
        if qt == QT_POD_HARD_SOLVERS:
            p = {"limit": limit}
            cc = ""
            bc = ""
            if college_name:
                cc = "AND c.name ILIKE :college"
                p["college"] = f"%{college_name}%"
            rows = db.execute(text(f"""
                SELECT u.first_name || ' ' || u.last_name AS name, c.name AS college,
                       COUNT(DISTINCT ps.question_id) AS hard_questions_solved
                FROM pod.pod_submission ps
                JOIN public.user u ON u.id = ps.user_id
                JOIN public.college c ON c.id = u.college_id
                WHERE ps.status = 'pass' AND ps.difficulty = 'hard'
                  AND u.role = 'Student' {cc}
                GROUP BY u.id, u.first_name, u.last_name, c.name
                ORDER BY hard_questions_solved DESC LIMIT :limit
            """), p).fetchall()
            return _rows_to_dicts(rows)

        # ── Longest streaks ───────────────────────────────────────────────────
        if qt == QT_POD_LONGEST_STREAK:
            p = {"limit": limit}
            cc = ""
            bc = ""
            if college_name:
                cc = "AND c.name ILIKE :college"
                p["college"] = f"%{college_name}%"
            rows = db.execute(text(f"""
                SELECT u.first_name || ' ' || u.last_name AS name, c.name AS college,
                       MAX(ps.streak_count) AS max_streak,
                       BOOL_OR(ps.is_active) AS has_active_streak
                FROM pod.pod_streak ps
                JOIN public.user u ON u.id = ps.user_id
                JOIN public.college c ON c.id = u.college_id
                WHERE u.role = 'Student' {cc}
                GROUP BY u.id, u.first_name, u.last_name, c.name
                ORDER BY max_streak DESC LIMIT :limit
            """), p).fetchall()
            return _rows_to_dicts(rows)

        # ── Active streaks ────────────────────────────────────────────────────
        if qt == QT_POD_ACTIVE_STREAKS:
            p = {"min_streak": min_streak, "limit": limit}
            cc = ""
            bc = ""
            if college_name:
                cc = "AND c.name ILIKE :college"
                p["college"] = f"%{college_name}%"
            rows = db.execute(text(f"""
                SELECT u.first_name || ' ' || u.last_name AS name, c.name AS college,
                       ps.streak_count, ps.start_date
                FROM pod.pod_streak ps
                JOIN public.user u ON u.id = ps.user_id
                JOIN public.college c ON c.id = u.college_id
                WHERE ps.is_active = true AND ps.streak_count >= :min_streak
                  AND u.role = 'Student' {cc}
                ORDER BY ps.streak_count DESC LIMIT :limit
            """), p).fetchall()
            return _rows_to_dicts(rows)

        # ── Lost streaks ──────────────────────────────────────────────────────
        if qt == QT_POD_LOST_STREAK:
            last_week = date.today() - timedelta(days=7)
            p = {"last_week": last_week, "limit": limit}
            cc = ""
            bc = ""
            if college_name:
                cc = "AND c.name ILIKE :college"
                p["college"] = f"%{college_name}%"
            rows = db.execute(text(f"""
                SELECT u.first_name || ' ' || u.last_name AS name, c.name AS college,
                       ps.streak_count AS lost_streak_count, ps.end_date::date AS lost_on
                FROM pod.pod_streak ps
                JOIN public.user u ON u.id = ps.user_id
                JOIN public.college c ON c.id = u.college_id
                WHERE ps.is_active = false AND ps.end_date::date >= :last_week
                  AND u.role = 'Student' {cc}
                ORDER BY ps.streak_count DESC LIMIT :limit
            """), p).fetchall()
            return _rows_to_dicts(rows)

        # ── Top coins ─────────────────────────────────────────────────────────
        if qt == QT_POD_TOP_COINS:
            p = {"limit": limit}
            cc = ""
            bc = ""
            if college_name:
                cc = "AND c.name ILIKE :college"
                p["college"] = f"%{college_name}%"
            rows = db.execute(text(f"""
                SELECT u.first_name || ' ' || u.last_name AS name, c.name AS college,
                       SUM(uc.coins_count) AS total_coins
                FROM pod.user_coins uc
                JOIN public.user u ON u.id = uc.user_id
                JOIN public.college c ON c.id = u.college_id
                WHERE u.role = 'Student' {cc}
                GROUP BY u.id, u.first_name, u.last_name, c.name
                ORDER BY total_coins DESC LIMIT :limit
            """), p).fetchall()
            return _rows_to_dicts(rows)

        # ── Total points today ────────────────────────────────────────────────
        if qt == QT_POD_TOTAL_POINTS_TODAY:
            p = {"today": date.today()}
            cc = ""
            bc = ""
            if college_name:
                cc = "AND c.name ILIKE :college"
                p["college"] = f"%{college_name}%"
            rows = db.execute(text(f"""
                SELECT c.name AS college,
                       SUM(ps.obtained_score) AS total_points_today,
                       COUNT(DISTINCT ps.user_id) AS students_participated
                FROM pod.pod_submission ps
                JOIN public.user u ON u.id = ps.user_id
                JOIN public.college c ON c.id = u.college_id
                WHERE ps.create_at::date = :today AND u.role = 'Student' {cc}
                GROUP BY c.name
            """), p).fetchall()
            return _rows_to_dicts(rows)

        # ── Top scorers ───────────────────────────────────────────────────────
        if qt == QT_POD_TOP_SCORERS:
            p = {"limit": limit}
            cc = ""
            wc = ""
            if college_name:
                cc = "AND c.name ILIKE :college"
                p["college"] = f"%{college_name}%"
            if week_filter:
                wc = "AND ps.create_at::date >= date_trunc('week', CURRENT_DATE)"
            rows = db.execute(text(f"""
                SELECT u.first_name || ' ' || u.last_name AS name, c.name AS college,
                       SUM(ps.obtained_score) AS total_score,
                       COUNT(DISTINCT ps.question_id) AS questions_attempted
                FROM pod.pod_submission ps
                JOIN public.user u ON u.id = ps.user_id
                JOIN public.college c ON c.id = u.college_id
                WHERE u.role = 'Student' {cc} {wc}
                GROUP BY u.id, u.first_name, u.last_name, c.name
                ORDER BY total_score DESC LIMIT :limit
            """), p).fetchall()
            return _rows_to_dicts(rows)

        # ── Daily trend ───────────────────────────────────────────────────────
        if qt == QT_POD_DAILY_TREND:
            _days = days if days else 30
            p = {"since": date.today() - timedelta(days=_days)}
            cc = ""
            if college_name:
                cc = "AND c.name ILIKE :college"
                p["college"] = f"%{college_name}%"
            rows = db.execute(text(f"""
                SELECT
                    pa.create_at::date                          AS attempt_date,
                    COUNT(DISTINCT pa.user_id)                  AS students_attempted,
                    COUNT(DISTINCT CASE WHEN ps.status = 'pass'
                        THEN ps.user_id END)                    AS students_passed,
                    COUNT(pa.id)                                AS total_attempts,
                    ROUND(
                        COUNT(DISTINCT CASE WHEN ps.status = 'pass' THEN ps.user_id END)*100.0
                        / NULLIF(COUNT(DISTINCT pa.user_id), 0), 2
                    )                                           AS pass_rate_percent
                FROM pod.pod_attempt pa
                JOIN public.user u ON u.id = pa.user_id
                JOIN public.college c ON c.id = u.college_id
                LEFT JOIN pod.pod_submission ps
                    ON ps.user_id = pa.user_id
                    AND ps.problem_of_the_day_id = pa.problem_of_the_day_id
                WHERE pa.create_at::date >= :since
                  AND u.role = 'Student' {cc}
                GROUP BY pa.create_at::date
                ORDER BY attempt_date DESC
            """), p).fetchall()
            return _rows_to_dicts(rows)

        # ── Badge earners ─────────────────────────────────────────────────────
        if qt == QT_POD_BADGE_EARNERS:
            p = {"limit": limit}
            cc = ""
            bc = ""
            if college_name:
                cc = "AND c.name ILIKE :college"
                p["college"] = f"%{college_name}%"
            rows = db.execute(text(f"""
                SELECT u.first_name || ' ' || u.last_name AS name, c.name AS college,
                       pb.name AS badge_name, pb.badge_type, upb.create_at AS earned_at
                FROM pod.user_pod_badge upb
                JOIN public.user u ON u.id = upb.user_id
                JOIN pod.pod_badge pb ON pb.id = upb.pod_badge_id
                JOIN public.college c ON c.id = u.college_id
                WHERE u.role = 'Student' {cc}
                ORDER BY upb.create_at DESC LIMIT :limit
            """), p).fetchall()
            return _rows_to_dicts(rows)

        # ── Weekly badge earners ──────────────────────────────────────────────
        if qt == QT_POD_WEEKLY_BADGE_EARNERS:
            week_start = date.today() - timedelta(days=date.today().weekday())
            p = {"week_start": week_start, "limit": limit}
            cc = ""
            bc = ""
            if college_name:
                cc = "AND c.name ILIKE :college"
                p["college"] = f"%{college_name}%"
            rows = db.execute(text(f"""
                SELECT u.first_name || ' ' || u.last_name AS name, c.name AS college,
                       pb.name AS badge_name, pb.badge_type, upb.create_at AS earned_at
                FROM pod.user_pod_badge upb
                JOIN public.user u ON u.id = upb.user_id
                JOIN pod.pod_badge pb ON pb.id = upb.pod_badge_id
                JOIN public.college c ON c.id = u.college_id
                WHERE upb.create_at::date >= :week_start AND u.role = 'Student' {cc}
                ORDER BY upb.create_at DESC LIMIT :limit
            """), p).fetchall()
            return _rows_to_dicts(rows)

        # ── Student profile ───────────────────────────────────────────────────
        if qt == QT_POD_STUDENT_PROFILE:
            if not student_name:
                return {}

            if date_filter == "today":
                date_clause = "AND ps.create_at::date = CURRENT_DATE"
            elif date_filter:
                date_clause = f"AND ps.create_at::date = '{date_filter}'"
            elif week_filter:
                date_clause = "AND ps.create_at::date >= date_trunc('week', CURRENT_DATE)"
            else:
                date_clause = ""

            p = {"student_name": f"%{student_name}%"}
            if college_name:
                p["college"] = f"%{college_name}%"

            college_clause   = "AND c.name ILIKE :college" if college_name else ""
            name_clause      = "AND (u.first_name || ' ' || u.last_name) ILIKE :student_name"
            language_clause  = ""
            if language:
                p["language"] = f"%{language}%"
                language_clause = "AND ps.language ILIKE :language"

            pod_type_join   = ""
            pod_type_clause = ""
            if pod_type:
                p["pod_type"] = pod_type.lower()
                pod_type_join   = "JOIN pod.problem_of_the_day potd ON potd.id = ps.problem_of_the_day_id"
                pod_type_clause = "AND potd.type = :pod_type"

            result = {}
            info_types = [i.strip() for i in info_type.replace(" and ", ",").split(",")]

            def should_fetch(section):
                return "all" in info_types or section in info_types

            if should_fetch("submissions"):
                rows = db.execute(text(f"""
                    SELECT u.first_name || ' ' || u.last_name AS name,
                           u.email, c.name AS college,
                           ps.title, ps.language, ps.difficulty,
                           ps.status, ps.obtained_score,
                           ps.create_at
                    FROM pod.pod_submission ps
                    JOIN public.user u ON u.id = ps.user_id
                    JOIN public.college c ON c.id = u.college_id
                    {pod_type_join}
                    WHERE u.role = 'Student'
                      {name_clause} {college_clause}
                      {date_clause} {language_clause} {pod_type_clause}
                    ORDER BY ps.create_at DESC LIMIT 20
                """), p).fetchall()
                result["submissions"] = _rows_to_dicts(rows)

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
                      {name_clause} {college_clause}
                    ORDER BY ps.streak_count DESC
                """), p).fetchall()
                result["streaks"] = _rows_to_dicts(rows)

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
                      {name_clause} {college_clause}
                    ORDER BY upb.create_at DESC
                """), p).fetchall()
                result["badges"] = _rows_to_dicts(rows)

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
                      {name_clause} {college_clause}
                    GROUP BY u.id, u.first_name, u.last_name, c.name
                """), p).fetchall()
                result["coins"] = _rows_to_dicts(rows)

            return result

        logger.warning(f"[get_pod_data] unknown query_type='{qt}'")
        return []

    except Exception as e:
        logger.error(f"[get_pod_data] query_type={qt} error: {e}")
        return []


# ══════════════════════════════════════════════════════════════════════════════
# EMPLOYABILITY DISPATCHER
# ══════════════════════════════════════════════════════════════════════════════

def get_emp_data(params: dict) -> Union[list[dict], dict]:
    """
    Single entry point for all Employability queries.
    params must include 'query_type' — one of the QT_EMP_* constants.
    """
    qt           = params.get("query_type", "")
    college_name = _normalize_college(params.get("college_name"))
    limit        = params.get("limit", 10)
    week_filter  = params.get("week_filter")
    domain_name  = _normalize_domain(params.get("domain_name"))
    difficulty   = params.get("difficulty")
    language     = params.get("language")
    date_filter  = params.get("date_filter")
    days         = params.get("days")
    student_name = params.get("student_name", "")

    try:
        db = next(get_db())

        # ── Top scorers ───────────────────────────────────────────────────────
        if qt == QT_EMP_TOP_SCORERS:
            p: dict = {"limit": limit}
            cc = ""
            bc = ""
            wc = ""
            if college_name:
                cc = "AND c.name ILIKE :college"
                p["college"] = f"%{college_name}%"
            if week_filter:
                wc = "AND ets.create_at >= date_trunc('week', CURRENT_TIMESTAMP)"
            rows = db.execute(text(f"""
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
                WHERE 1=1 {cc} {wc}
                GROUP BY u.id, u.first_name, u.last_name, u.email, c.name
                ORDER BY total_score DESC
                LIMIT :limit
            """), p).fetchall()
            return _rows_to_dicts(rows)

        # ── Difficulty stats ──────────────────────────────────────────────────
        if qt == QT_EMP_DIFFICULTY_STATS:
            p = {}
            cc = ""
            bc = ""
            if college_name:
                cc = "AND c.name ILIKE :college"
                p["college"] = f"%{college_name}%"
            rows = db.execute(text(f"""
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
                WHERE ets.difficulty IS NOT NULL {cc}
                GROUP BY ets.difficulty
                ORDER BY CASE ets.difficulty
                    WHEN 'easy'   THEN 1
                    WHEN 'medium' THEN 2
                    WHEN 'hard'   THEN 3
                    ELSE 4
                END
            """), p).fetchall()
            return _rows_to_dicts(rows)

        # ── Language stats ────────────────────────────────────────────────────
        if qt == QT_EMP_LANGUAGE_STATS:
            p = {}
            cc = ""
            bc = ""
            if college_name:
                cc = "AND c.name ILIKE :college"
                p["college"] = f"%{college_name}%"
            rows = db.execute(text(f"""
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
                WHERE ets.language IS NOT NULL {cc}
                GROUP BY ets.language
                ORDER BY total_submissions DESC
            """), p).fetchall()
            return _rows_to_dicts(rows)

        # ── Domain breakdown ──────────────────────────────────────────────────
        if qt == QT_EMP_DOMAIN_BREAKDOWN:
            p = {}
            cc = ""
            dc = ""
            if college_name:
                cc = "AND c.name ILIKE :college"
                p["college"] = f"%{college_name}%"
            if domain_name:
                dc = "AND d.domain ILIKE :domain"
                p["domain"] = f"%{domain_name}%"
            rows = db.execute(text(f"""
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
                WHERE 1=1 {cc} {dc}
                GROUP BY d.domain
                ORDER BY total_submissions DESC
            """), p).fetchall()
            return _rows_to_dicts(rows)

        # ── Subdomain breakdown ───────────────────────────────────────────────
        if qt == QT_EMP_SUBDOMAIN_BREAKDOWN:
            p = {"limit": limit}
            cc = ""
            dc = ""
            if college_name:
                cc = "AND c.name ILIKE :college"
                p["college"] = f"%{college_name}%"
            if domain_name:
                dc = "AND d.domain ILIKE :domain"
                p["domain"] = f"%{domain_name}%"
            rows = db.execute(text(f"""
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
                WHERE 1=1 {cc} {dc}
                GROUP BY d.domain, qsd.name
                ORDER BY total_submissions DESC
                LIMIT :limit
            """), p).fetchall()
            return _rows_to_dicts(rows)

        # ── Question type stats ───────────────────────────────────────────────
        if qt == QT_EMP_QUESTION_TYPE_STATS:
            p = {}
            cc = ""
            bc = ""
            if college_name:
                cc = "AND c.name ILIKE :college"
                p["college"] = f"%{college_name}%"
            rows = db.execute(text(f"""
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
                WHERE 1=1 {cc}
                GROUP BY tt.name
                ORDER BY total_submissions DESC
            """), p).fetchall()
            return _rows_to_dicts(rows)

        # ── Most solved ───────────────────────────────────────────────────────
        if qt == QT_EMP_MOST_SOLVED:
            p = {"limit": limit}
            cc = ""
            bc = ""
            if college_name:
                cc = "AND c.name ILIKE :college"
                p["college"] = f"%{college_name}%"
            rows = db.execute(text(f"""
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
                WHERE 1=1 {cc}
                GROUP BY u.id, u.first_name, u.last_name, u.email, c.name
                ORDER BY solved_count DESC
                LIMIT :limit
            """), p).fetchall()
            return _rows_to_dicts(rows)

        # ── Recent activity ───────────────────────────────────────────────────
        if qt == QT_EMP_RECENT_ACTIVITY:
            p = {"limit": limit}
            cc = ""
            dc = ""
            difc = ""
            lc = ""
            if college_name:
                cc = "AND c.name ILIKE :college"
                p["college"] = f"%{college_name}%"
            if date_filter == "today":
                dc = "AND ets.create_at::date = CURRENT_DATE"
            elif date_filter:
                dc = f"AND ets.create_at::date = '{date_filter}'"
            elif days:
                dc = "AND ets.create_at >= NOW() - (:days * INTERVAL '1 day')"
                p["days"] = days
            if difficulty:
                difc = "AND ets.difficulty ILIKE :difficulty"
                p["difficulty"] = difficulty
            if language:
                lc = "AND ets.language ILIKE :language"
                p["language"] = f"%{language}%"
            rows = db.execute(text(f"""
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
                WHERE 1=1 {cc} {dc} {difc} {lc}
                ORDER BY ets.create_at DESC
                LIMIT :limit
            """), p).fetchall()
            return _rows_to_dicts(rows)

        # ── Hardest questions ─────────────────────────────────────────────────
        if qt == QT_EMP_HARDEST_QUESTIONS:
            p = {"limit": limit}
            cc = ""
            difc = ""
            if college_name:
                cc = "AND c.name ILIKE :college"
                p["college"] = f"%{college_name}%"
            if difficulty:
                difc = "AND ets.difficulty ILIKE :difficulty"
                p["difficulty"] = difficulty
            rows = db.execute(text(f"""
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
                WHERE 1=1 {cc} {difc}
                GROUP BY ets.question_id
                HAVING COUNT(ets.id) >= 5
                ORDER BY pass_rate_percent ASC, total_attempts DESC
                LIMIT :limit
            """), p).fetchall()
            return _rows_to_dicts(rows)

        # ── Daily trend ───────────────────────────────────────────────────────
        if qt == QT_EMP_DAILY_TREND:
            _days = days if days else 30
            p = {"since": date.today() - timedelta(days=_days)}
            cc = ""
            bc = ""
            if college_name:
                cc = "AND c.name ILIKE :college"
                p["college"] = f"%{college_name}%"
            rows = db.execute(text(f"""
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
                WHERE ets.create_at::date >= :since {cc}
                GROUP BY ets.create_at::date
                ORDER BY submission_date DESC
            """), p).fetchall()
            return _rows_to_dicts(rows)

        # ── Pass rate ─────────────────────────────────────────────────────────
        if qt == QT_EMP_PASS_RATE:
            p = {}
            cc = ""
            bc = ""
            if college_name:
                cc = "AND c.name ILIKE :college"
                p["college"] = f"%{college_name}%"
            rows = db.execute(text(f"""
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
                WHERE 1=1 {cc}
                GROUP BY c.name
                ORDER BY pass_rate_percent DESC
            """), p).fetchall()
            return _rows_to_dicts(rows)

        # ── Domain students ───────────────────────────────────────────────────
        if qt == QT_EMP_DOMAIN_STUDENTS:
            if not domain_name:
                return []
            p: dict = {"domain": f"%{domain_name}%", "limit": limit}
            cc = ""
            bc = ""
            if college_name:
                cc = "AND c.name ILIKE :college"
                p["college"] = f"%{college_name}%"
            rows = db.execute(text(f"""
                SELECT
                    u.first_name || ' ' || u.last_name  AS name,
                    u.email,
                    c.name                              AS college,
                    d.domain                            AS domain,
                    COUNT(ets.id)                       AS total_submissions,
                    COUNT(CASE WHEN ets.status = 'pass' THEN 1 END) AS total_passed,
                    COUNT(CASE WHEN ets.status = 'fail' THEN 1 END) AS total_failed,
                    ROUND(
                        COUNT(CASE WHEN ets.status = 'pass' THEN 1 END)*100.0
                        / NULLIF(COUNT(ets.id), 0), 2
                    )                                   AS pass_rate_percent,
                    SUM(ets.obtained_score)             AS total_score
                FROM employability_track.employability_track_submission ets
                JOIN public.domains  d ON d.id  = ets.domain_id
                JOIN public.user     u ON u.id  = ets.user_id
                JOIN public.college  c ON c.id  = u.college_id
                WHERE d.domain ILIKE :domain {cc}
                GROUP BY u.id, u.first_name, u.last_name, u.email, c.name, d.domain
                ORDER BY total_passed DESC, total_score DESC
                LIMIT :limit
            """), p).fetchall()
            return _rows_to_dicts(rows)

        # ── User profile ──────────────────────────────────────────────────────
        if qt == QT_EMP_USER_PROFILE:
            if not student_name:
                return {"summary": [], "submissions": [], "question_status": []}

            base_p: dict = {"name": f"%{student_name}%"}
            cc = ""
            if college_name:
                cc = "AND c.name ILIKE :college"
                base_p["college"] = f"%{college_name}%"

            sub_p = dict(base_p)
            filters = ""
            if difficulty:
                filters += " AND ets.difficulty ILIKE :difficulty"
                sub_p["difficulty"] = difficulty
            if language:
                filters += " AND ets.language ILIKE :language"
                sub_p["language"] = f"%{language}%"
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
                  {cc} {filters}
                ORDER BY ets.create_at DESC
                LIMIT 50
            """), sub_p).fetchall()

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
                WHERE (u.first_name || ' ' || u.last_name) ILIKE :name {cc}
                GROUP BY u.id, u.first_name, u.last_name, c.name
            """), base_p).fetchall()

            question_status = db.execute(text(f"""
                SELECT
                    qs.status,
                    COUNT(qs.question_id) AS question_count
                FROM employability_track.question_status qs
                JOIN public.user    u ON u.id = qs.user_id
                JOIN public.college c ON c.id = u.college_id
                WHERE (u.first_name || ' ' || u.last_name) ILIKE :name {cc}
                GROUP BY qs.status
            """), base_p).fetchall()

            return {
                "summary":         _rows_to_dicts(summary),
                "submissions":     _rows_to_dicts(submissions),
                "question_status": _rows_to_dicts(question_status),
            }

        logger.warning(f"[get_emp_data] unknown query_type='{qt}'")
        return []

    except Exception as e:
        logger.error(f"[get_emp_data] query_type={qt} error: {e}")
        return []


# ══════════════════════════════════════════════════════════════════════════════
# ASSESSMENT DISPATCHER
# ══════════════════════════════════════════════════════════════════════════════

def get_assess_data(params: dict) -> Union[list[dict], dict]:
    """
    Single entry point for all Assessment queries.
    params must include 'query_type' — one of the QT_ASSESS_* constants.
    """
    qt               = params.get("query_type", "")
    assessment_title = params.get("assessment_title")
    student_name     = params.get("student_name", "")
    limit            = params.get("limit", 10)

    try:
        db = next(get_db())

        # ── List assessments ──────────────────────────────────────────────────
        if qt == QT_ASSESS_LIST:
            p: dict = {}
            tc = _assess_title_clause(assessment_title, p)
            rows = db.execute(text(f"""
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
                WHERE 1=1 {tc}
                ORDER BY a.created_at DESC
            """), p).fetchall()
            return _rows_to_dicts(rows)

        # ── Overview ──────────────────────────────────────────────────────────
        if qt == QT_ASSESS_OVERVIEW:
            p = {}
            tc = _assess_title_clause(assessment_title, p)
            rows = db.execute(text(f"""
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
                WHERE 1=1 {tc}
                GROUP BY a.id, a.assessment_title, a.status, a.open_time,
                         a.close_time, a.shortlisted_students, a.assessment_submitted_students
                ORDER BY a.created_at DESC
            """), p).fetchall()
            return _rows_to_dicts(rows)

        # ── Student result ────────────────────────────────────────────────────
        if qt == QT_ASSESS_STUDENT_RESULT:
            if not student_name:
                return []
            p = {"name": f"%{student_name}%"}
            tc = _assess_title_clause(assessment_title, p)
            rows = db.execute(text(f"""
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
                  {tc}
                ORDER BY s.submission_time DESC
                LIMIT 50
            """), p).fetchall()
            return _rows_to_dicts(rows)

        # ── Top scorers ───────────────────────────────────────────────────────
        if qt == QT_ASSESS_TOP_SCORERS:
            p = {"limit": limit}
            tc = _assess_title_clause(assessment_title, p)
            rows = db.execute(text(f"""
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
                WHERE 1=1 {tc}
                GROUP BY u.id, u.first_name, u.last_name, u.email, a.assessment_title
                ORDER BY total_score DESC
                LIMIT :limit
            """), p).fetchall()

            if not rows:
                rows = db.execute(text(f"""
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
                    WHERE 1=1 {tc}
                    GROUP BY u.id, u.first_name, u.last_name, u.email, a.assessment_title
                    ORDER BY total_score DESC
                    LIMIT :limit
                """), p).fetchall()

            return _rows_to_dicts(rows)

        # ── Pass rate ─────────────────────────────────────────────────────────
        if qt == QT_ASSESS_PASS_RATE:
            p = {}
            tc = _assess_title_clause(assessment_title, p)
            rows = db.execute(text(f"""
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
                WHERE 1=1 {tc}
                GROUP BY a.id, a.assessment_title, a.status
                ORDER BY pass_rate_percent DESC
            """), p).fetchall()
            return _rows_to_dicts(rows)

        # ── Skill breakdown ───────────────────────────────────────────────────
        if qt == QT_ASSESS_SKILL_BREAKDOWN:
            p = {}
            tc = _assess_title_clause(assessment_title, p)
            rows = db.execute(text(f"""
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
                WHERE s.skill IS NOT NULL {tc}
                GROUP BY a.assessment_title, s.skill
                ORDER BY total_submissions DESC
            """), p).fetchall()
            return _rows_to_dicts(rows)

        # ── Difficulty breakdown ──────────────────────────────────────────────
        if qt == QT_ASSESS_DIFFICULTY_BREAKDOWN:
            p = {}
            tc = _assess_title_clause(assessment_title, p)
            rows = db.execute(text(f"""
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
                WHERE s.difficulty IS NOT NULL {tc}
                GROUP BY a.assessment_title, s.difficulty
                ORDER BY a.assessment_title,
                         CASE s.difficulty WHEN 'easy' THEN 1 WHEN 'medium' THEN 2 WHEN 'hard' THEN 3 ELSE 4 END
            """), p).fetchall()

            if not rows:
                rows = db.execute(text(f"""
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
                    JOIN gest.assessment_shortlist a ON a.hackathon_id = s.round_id
                    WHERE 1=1 {tc}
                    GROUP BY a.assessment_title
                """), p).fetchall()

            return _rows_to_dicts(rows)

        # ── Completion rate ───────────────────────────────────────────────────
        if qt == QT_ASSESS_COMPLETION_RATE:
            p = {}
            tc = _assess_title_clause(assessment_title, p)
            rows = db.execute(text(f"""
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
                WHERE 1=1 {tc}
                GROUP BY a.id, a.assessment_title, a.status,
                         a.shortlisted_students, a.assessment_submitted_students
                ORDER BY a.created_at DESC
            """), p).fetchall()
            return _rows_to_dicts(rows)

        # ── Recent ────────────────────────────────────────────────────────────
        if qt == QT_ASSESS_RECENT:
            rows = db.execute(text("""
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
            return _rows_to_dicts(rows)

        # ── Student attempts ──────────────────────────────────────────────────
        if qt == QT_ASSESS_STUDENT_ATTEMPTS:
            if not student_name:
                return []
            rows = db.execute(text("""
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

            if not rows:
                rows = db.execute(text("""
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

            return _rows_to_dicts(rows)

        # ── Shortlisted but not submitted ─────────────────────────────────────
        if qt == QT_ASSESS_SHORTLISTED_NOT_SUBMITTED:
            p: dict = {"limit": limit}
            tc = _assess_title_clause(assessment_title, p)
            if assessment_title:
                # Specific assessment — show one row per student with assessment title
                rows = db.execute(text(f"""
                    SELECT
                        a.assessment_title                      AS assessment,
                        u.first_name || ' ' || u.last_name     AS name,
                        u.email,
                        c.name                                  AS college
                    FROM gest.assessment_shortlist a
                    JOIN public.user u
                        ON u.id::text = ANY(
                            SELECT jsonb_array_elements_text(a.shortlisted_students)
                        )
                    LEFT JOIN public.college c ON c.id = u.college_id
                    WHERE NOT (
                        u.id::text = ANY(
                            SELECT jsonb_array_elements_text(a.assessment_submitted_students)
                        )
                    )
                    AND 1=1 {tc}
                    ORDER BY u.first_name
                    LIMIT :limit
                """), p).fetchall()
            else:
                # No assessment filter — return distinct students with count of missed assessments
                rows = db.execute(text("""
                    SELECT
                        u.first_name || ' ' || u.last_name     AS name,
                        u.email,
                        c.name                                  AS college,
                        COUNT(DISTINCT a.id)                    AS assessments_missed
                    FROM gest.assessment_shortlist a
                    JOIN public.user u
                        ON u.id::text = ANY(
                            SELECT jsonb_array_elements_text(a.shortlisted_students)
                        )
                    LEFT JOIN public.college c ON c.id = u.college_id
                    WHERE NOT (
                        u.id::text = ANY(
                            SELECT jsonb_array_elements_text(a.assessment_submitted_students)
                        )
                    )
                    GROUP BY u.id, u.first_name, u.last_name, u.email, c.name
                    ORDER BY assessments_missed DESC, u.first_name
                    LIMIT :limit
                """), p).fetchall()
            return _rows_to_dicts(rows)

        # ── Passed students ───────────────────────────────────────────────────
        if qt == QT_ASSESS_PASSED_STUDENTS:
            p: dict = {"limit": limit}
            tc = _assess_title_clause(assessment_title, p)
            rows = db.execute(text(f"""
                SELECT
                    u.first_name || ' ' || u.last_name         AS name,
                    u.email,
                    c.name                                      AS college,
                    a.assessment_title                          AS assessment,
                    COUNT(CASE WHEN s.status = 'pass' THEN 1 END) AS questions_passed,
                    COUNT(s.id)                                 AS total_questions,
                    SUM(s.obtained_score)                       AS total_score,
                    ROUND(
                        COUNT(CASE WHEN s.status = 'pass' THEN 1 END)*100.0
                        / NULLIF(COUNT(s.id), 0), 2
                    )                                           AS pass_rate_percent
                FROM gest.assessment_final_attempt_submission s
                JOIN public.user u ON u.id = s.user_id
                LEFT JOIN public.college c ON c.id = u.college_id
                JOIN gest.assessment_shortlist a ON a.id::text = s.assessment_id
                WHERE 1=1 {tc}
                GROUP BY u.id, u.first_name, u.last_name, u.email, c.name, a.assessment_title
                HAVING COUNT(CASE WHEN s.status = 'pass' THEN 1 END) > 0
                ORDER BY questions_passed DESC, total_score DESC
                LIMIT :limit
            """), p).fetchall()
            return _rows_to_dicts(rows)

        logger.warning(f"[get_assess_data] unknown query_type='{qt}'")
        return []

    except Exception as e:
        logger.error(f"[get_assess_data] query_type={qt} error: {e}")
        return []