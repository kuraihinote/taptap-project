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
INTENT_UNKNOWN                    = "unknown"

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
    INTENT_UNKNOWN,
]