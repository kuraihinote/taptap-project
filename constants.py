# constants.py — TapTap POD Analytics Chatbot
# Central config — loads and validates all environment variables.
# All other files import from here instead of calling os.getenv() directly.

from dotenv import load_dotenv
import os
load_dotenv()


# ── Database ──────────────────────────────────────────────────────────────────

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise Exception("DATABASE_URL not found in environment variables.")


# ── Azure OpenAI ──────────────────────────────────────────────────────────────

AZURE_GPT4O_MINI_CONFIG = {
    "api_key":         os.getenv("AZURE_OPENAI_API_KEY"),
    "api_version":     os.getenv("AZURE_OPENAI_API_VERSION"),
    "azure_endpoint":  os.getenv("AZURE_OPENAI_ENDPOINT"),
    "deployment_name": os.getenv("AZURE_OPENAI_DEPLOYMENT"),
}

if not all(AZURE_GPT4O_MINI_CONFIG.values()):
    raise Exception("Azure OpenAI config details not found in environment variables.")


# ── LLM settings ──────────────────────────────────────────────────────────────

LLM_TEMPERATURE = 0.0
LLM_MAX_TOKENS  = 512


# ── POD Intent Labels ─────────────────────────────────────────────────────────

INTENT_POD_WHO_SOLVED_TODAY       = "pod_who_solved_today"
INTENT_POD_ATTEMPT_COUNT_TODAY    = "pod_attempt_count_today"
INTENT_POD_QUESTION_TODAY         = "pod_question_today"
INTENT_POD_FASTEST_SOLVER         = "pod_fastest_solver"
INTENT_POD_NOT_ATTEMPTED_TODAY    = "pod_not_attempted_today"
INTENT_POD_PASS_FAIL_SUMMARY      = "pod_pass_fail_summary"
INTENT_POD_PASS_RATE              = "pod_pass_rate"
INTENT_POD_TOP_PASSERS            = "pod_top_passers"
INTENT_POD_NEVER_PASSED           = "pod_never_passed"
INTENT_POD_WEEKLY_PASSERS         = "pod_weekly_passers"
INTENT_POD_DIFFICULTY_BREAKDOWN   = "pod_difficulty_breakdown"
INTENT_POD_LANGUAGE_BREAKDOWN     = "pod_language_breakdown"
INTENT_POD_HARD_SOLVERS           = "pod_hard_solvers"
INTENT_POD_LONGEST_STREAK         = "pod_longest_streak"
INTENT_POD_ACTIVE_STREAKS         = "pod_active_streaks"
INTENT_POD_LOST_STREAK            = "pod_lost_streak"
INTENT_POD_TOP_COINS              = "pod_top_coins"
INTENT_POD_TOTAL_POINTS_TODAY     = "pod_total_points_today"
INTENT_POD_TOP_SCORERS            = "pod_top_scorers"
INTENT_POD_BADGE_EARNERS          = "pod_badge_earners"
INTENT_POD_WEEKLY_BADGE_EARNERS   = "pod_weekly_badge_earners"
INTENT_POD_STUDENT_PROFILE        = "pod_student_profile"
INTENT_UNKNOWN                    = "unknown"


# ── Employability Intent Labels ───────────────────────────────────────────────

INTENT_EMP_TOP_SCORERS            = "emp_top_scorers"
INTENT_EMP_DIFFICULTY_STATS       = "emp_difficulty_stats"
INTENT_EMP_LANGUAGE_STATS         = "emp_language_stats"
INTENT_EMP_DOMAIN_BREAKDOWN       = "emp_domain_breakdown"
INTENT_EMP_SUBDOMAIN_BREAKDOWN    = "emp_subdomain_breakdown"
INTENT_EMP_QUESTION_TYPE_STATS    = "emp_question_type_stats"
INTENT_EMP_MOST_SOLVED            = "emp_most_solved"
INTENT_EMP_RECENT_ACTIVITY        = "emp_recent_activity"
INTENT_EMP_HARDEST_QUESTIONS      = "emp_hardest_questions"
INTENT_EMP_DAILY_TREND            = "emp_daily_trend"
INTENT_EMP_PASS_RATE              = "emp_pass_rate"
INTENT_EMP_USER_PROFILE           = "emp_user_profile"


# ── Assess Intent Labels ──────────────────────────────────────────────────────

INTENT_ASSESS_LIST                = "assess_list"
INTENT_ASSESS_OVERVIEW            = "assess_overview"
INTENT_ASSESS_STUDENT_RESULT      = "assess_student_result"
INTENT_ASSESS_TOP_SCORERS         = "assess_top_scorers"
INTENT_ASSESS_PASS_RATE           = "assess_pass_rate"
INTENT_ASSESS_SKILL_BREAKDOWN     = "assess_skill_breakdown"
INTENT_ASSESS_DIFFICULTY_BREAKDOWN= "assess_difficulty_breakdown"
INTENT_ASSESS_COMPLETION_RATE     = "assess_completion_rate"
INTENT_ASSESS_RECENT              = "assess_recent"
INTENT_ASSESS_STUDENT_ATTEMPTS    = "assess_student_attempts"


ALL_INTENTS = [
    INTENT_POD_WHO_SOLVED_TODAY,
    INTENT_POD_ATTEMPT_COUNT_TODAY,
    INTENT_POD_QUESTION_TODAY,
    INTENT_POD_FASTEST_SOLVER,
    INTENT_POD_NOT_ATTEMPTED_TODAY,
    INTENT_POD_PASS_FAIL_SUMMARY,
    INTENT_POD_PASS_RATE,
    INTENT_POD_TOP_PASSERS,
    INTENT_POD_NEVER_PASSED,
    INTENT_POD_WEEKLY_PASSERS,
    INTENT_POD_DIFFICULTY_BREAKDOWN,
    INTENT_POD_LANGUAGE_BREAKDOWN,
    INTENT_POD_HARD_SOLVERS,
    INTENT_POD_LONGEST_STREAK,
    INTENT_POD_ACTIVE_STREAKS,
    INTENT_POD_LOST_STREAK,
    INTENT_POD_TOP_COINS,
    INTENT_POD_TOTAL_POINTS_TODAY,
    INTENT_POD_TOP_SCORERS,
    INTENT_POD_BADGE_EARNERS,
    INTENT_POD_WEEKLY_BADGE_EARNERS,
    INTENT_POD_STUDENT_PROFILE,
    # Employability
    INTENT_EMP_TOP_SCORERS,
    INTENT_EMP_DIFFICULTY_STATS,
    INTENT_EMP_LANGUAGE_STATS,
    INTENT_EMP_DOMAIN_BREAKDOWN,
    INTENT_EMP_SUBDOMAIN_BREAKDOWN,
    INTENT_EMP_QUESTION_TYPE_STATS,
    INTENT_EMP_MOST_SOLVED,
    INTENT_EMP_RECENT_ACTIVITY,
    INTENT_EMP_HARDEST_QUESTIONS,
    INTENT_EMP_DAILY_TREND,
    INTENT_EMP_PASS_RATE,
    INTENT_EMP_USER_PROFILE,
    # Assess
    INTENT_ASSESS_LIST,
    INTENT_ASSESS_OVERVIEW,
    INTENT_ASSESS_STUDENT_RESULT,
    INTENT_ASSESS_TOP_SCORERS,
    INTENT_ASSESS_PASS_RATE,
    INTENT_ASSESS_SKILL_BREAKDOWN,
    INTENT_ASSESS_DIFFICULTY_BREAKDOWN,
    INTENT_ASSESS_COMPLETION_RATE,
    INTENT_ASSESS_RECENT,
    INTENT_ASSESS_STUDENT_ATTEMPTS,
    INTENT_UNKNOWN,
]