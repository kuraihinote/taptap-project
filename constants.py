# constants.py — TapTap Analytics Chatbot
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


# ── Top-level domain intents (replaces 44 narrow intents) ─────────────────────

INTENT_POD       = "pod"
INTENT_EMP       = "emp"
INTENT_ASSESS    = "assess"
INTENT_UNKNOWN   = "unknown"
INTENT_AMBIGUOUS = "ambiguous"

ALL_INTENTS = [INTENT_POD, INTENT_EMP, INTENT_ASSESS, INTENT_UNKNOWN]


# ── POD query_type sub-labels ──────────────────────────────────────────────────
# Passed inside params["query_type"] by the LLM.
# Values deliberately match old narrow intent names for streamlit chart routing.

QT_POD_WHO_SOLVED_TODAY       = "pod_who_solved_today"
QT_POD_ATTEMPT_COUNT_TODAY    = "pod_attempt_count_today"
QT_POD_QUESTION_TODAY         = "pod_question_today"
QT_POD_FASTEST_SOLVER         = "pod_fastest_solver"
QT_POD_NOT_ATTEMPTED_TODAY    = "pod_not_attempted_today"
QT_POD_PASS_FAIL_SUMMARY      = "pod_pass_fail_summary"
QT_POD_PASS_RATE              = "pod_pass_rate"
QT_POD_TOP_PASSERS            = "pod_top_passers"
QT_POD_NEVER_PASSED           = "pod_never_passed"
QT_POD_WEEKLY_PASSERS         = "pod_weekly_passers"
QT_POD_DIFFICULTY_BREAKDOWN   = "pod_difficulty_breakdown"
QT_POD_LANGUAGE_BREAKDOWN     = "pod_language_breakdown"
QT_POD_HARD_SOLVERS           = "pod_hard_solvers"
QT_POD_LONGEST_STREAK         = "pod_longest_streak"
QT_POD_ACTIVE_STREAKS         = "pod_active_streaks"
QT_POD_LOST_STREAK            = "pod_lost_streak"
QT_POD_TOP_COINS              = "pod_top_coins"
QT_POD_TOTAL_POINTS_TODAY     = "pod_total_points_today"
QT_POD_TOP_SCORERS            = "pod_top_scorers"
QT_POD_BADGE_EARNERS          = "pod_badge_earners"
QT_POD_WEEKLY_BADGE_EARNERS   = "pod_weekly_badge_earners"
QT_POD_DAILY_TREND            = "pod_daily_trend"
QT_POD_STUDENT_PROFILE        = "pod_student_profile"

# ── Employability query_type sub-labels ───────────────────────────────────────

QT_EMP_TOP_SCORERS            = "emp_top_scorers"
QT_EMP_DIFFICULTY_STATS       = "emp_difficulty_stats"
QT_EMP_LANGUAGE_STATS         = "emp_language_stats"
QT_EMP_DOMAIN_BREAKDOWN       = "emp_domain_breakdown"
QT_EMP_SUBDOMAIN_BREAKDOWN    = "emp_subdomain_breakdown"
QT_EMP_QUESTION_TYPE_STATS    = "emp_question_type_stats"
QT_EMP_MOST_SOLVED            = "emp_most_solved"
QT_EMP_RECENT_ACTIVITY        = "emp_recent_activity"
QT_EMP_HARDEST_QUESTIONS      = "emp_hardest_questions"
QT_EMP_DAILY_TREND            = "emp_daily_trend"
QT_EMP_PASS_RATE              = "emp_pass_rate"
QT_EMP_DOMAIN_STUDENTS        = "emp_domain_students"
QT_EMP_USER_PROFILE           = "emp_user_profile"

# ── Assessment query_type sub-labels ──────────────────────────────────────────

QT_ASSESS_LIST                = "assess_list"
QT_ASSESS_OVERVIEW            = "assess_overview"
QT_ASSESS_STUDENT_RESULT      = "assess_student_result"
QT_ASSESS_TOP_SCORERS         = "assess_top_scorers"
QT_ASSESS_PASS_RATE           = "assess_pass_rate"
QT_ASSESS_SKILL_BREAKDOWN     = "assess_skill_breakdown"
QT_ASSESS_DIFFICULTY_BREAKDOWN= "assess_difficulty_breakdown"
QT_ASSESS_COMPLETION_RATE     = "assess_completion_rate"
QT_ASSESS_RECENT                    = "assess_recent"
QT_ASSESS_STUDENT_ATTEMPTS          = "assess_student_attempts"
QT_ASSESS_SHORTLISTED_NOT_SUBMITTED = "assess_shortlisted_not_submitted"
QT_ASSESS_PASSED_STUDENTS           = "assess_passed_students"