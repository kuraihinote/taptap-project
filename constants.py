# constants.py — TapTap Analytics Chatbot (LLM Query Generation approach)
# Central config — loads and validates all environment variables.

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

LLM_TEMPERATURE     = 0.0
LLM_MAX_TOKENS      = 512
SQL_LLM_MAX_TOKENS  = 1024   # SQL generation needs more tokens than classification


# ── Domain intents ────────────────────────────────────────────────────────────

INTENT_POD       = "pod"
INTENT_EMP       = "emp"
INTENT_ASSESS    = "assess"
INTENT_UNKNOWN   = "unknown"
INTENT_AMBIGUOUS = "ambiguous"


# ── SQL safety ────────────────────────────────────────────────────────────────

SQL_MAX_ROWS  = 50   # Hard limit injected into every generated query
SQL_MAX_CHAIN = 3    # Max follow-up SQL modifications before regenerating from scratch