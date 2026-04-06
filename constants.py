# constants.py — TapTap Analytics Chatbot
# Central config — loads and validates all environment variables.

from dotenv import load_dotenv
import os
load_dotenv("../.env")


# ── Production DB (read-only) ─────────────────────────────────────────────────
# Used by analytics.py / db.py for all student data queries.

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise Exception("DATABASE_URL not found in environment variables.")


# ── Stage DB (writable) — Checkpoint saver only ───────────────────────────────
# LangGraph AsyncPostgresSaver creates its own tables here.
# Falls back to None → InMemorySaver used instead (safe for local dev without stage creds).

_CHECKPOINT_HOST     = os.getenv("CHECKPOINT_DB_HOST", "")
_CHECKPOINT_PORT     = os.getenv("CHECKPOINT_DB_PORT", "5432")
_CHECKPOINT_NAME     = os.getenv("CHECKPOINT_DB_NAME", "")
_CHECKPOINT_USER     = os.getenv("CHECKPOINT_DB_USER", "")
_CHECKPOINT_PASSWORD = os.getenv("CHECKPOINT_DB_PASSWORD", "")

# Only build the URL if all required parts are present
if all([_CHECKPOINT_HOST, _CHECKPOINT_NAME, _CHECKPOINT_USER, _CHECKPOINT_PASSWORD]):
    # asyncpg driver required by AsyncPostgresSaver
    CHECKPOINT_DB_URL = (
        f"postgresql://{_CHECKPOINT_USER}:{_CHECKPOINT_PASSWORD}"
        f"@{_CHECKPOINT_HOST}:{_CHECKPOINT_PORT}/{_CHECKPOINT_NAME}"
        f"?sslmode=require"
    )
else:
    CHECKPOINT_DB_URL = None  # triggers InMemorySaver fallback in llm.py


# ── Azure OpenAI ──────────────────────────────────────────────────────────────

AZURE_GPT4O_MINI_CONFIG = {
    "api_key":         os.getenv("AZURE_OPENAI_API_KEY"),
    "api_version":     os.getenv("AZURE_OPENAI_API_VERSION"),
    "azure_endpoint":  os.getenv("AZURE_OPENAI_ENDPOINT"),
    "deployment_name": os.getenv("AZURE_OPENAI_DEPLOYMENT"),
}

if not all(AZURE_GPT4O_MINI_CONFIG.values()):
    raise Exception("Azure OpenAI config details not found in environment variables.")


# ── Domain intents ────────────────────────────────────────────────────────────

INTENT_POD       = "pod"
INTENT_EMP       = "emp"
INTENT_ASSESS    = "assess"
INTENT_UNKNOWN   = "unknown"
INTENT_AMBIGUOUS = "ambiguous"


# ── SQL safety ────────────────────────────────────────────────────────────────

SQL_MAX_ROWS  = 50   # Hard limit injected into every generated query
SQL_MAX_CHAIN = 3    # Max follow-up SQL modifications before regenerating from scratch


# ── Checkpoint / conversation memory ─────────────────────────────────────────

# Dummy faculty ID used until real auth is wired from the frontend.
# Replace with the actual faculty ID received from the frontend in production.
DUMMY_FACULTY_ID = "faculty_001"