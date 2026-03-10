# constants.py — TapTap Analytics Chatbot v3

# Employability band labels
EMPLOYABILITY_BANDS = ["High", "Medium", "Low", "Very Low"]

# Role values in DB
STUDENT_ROLE = "Student"

# Pod submission statuses
POD_STATUS_PASS = "pass"
POD_STATUS_FAIL = "fail"

# Default pagination
DEFAULT_LIMIT = 50
MAX_LIMIT = 500

# Intent labels (used by LLM classifier)
INTENT_TOP_STUDENTS          = "top_students"
INTENT_BOTTOM_STUDENTS       = "bottom_students"
INTENT_BAND_DISTRIBUTION     = "band_distribution"
INTENT_COLLEGE_SUMMARY       = "college_summary"
INTENT_DEPARTMENT_SUMMARY    = "department_summary"
INTENT_HACKATHON_PERFORMANCE = "hackathon_performance"
INTENT_POD_PERFORMANCE       = "pod_performance"
INTENT_STUDENT_PROFILE       = "student_profile"
INTENT_SCORE_DISTRIBUTION    = "score_distribution"
INTENT_UNKNOWN               = "unknown"

ALL_INTENTS = [
    INTENT_TOP_STUDENTS,
    INTENT_BOTTOM_STUDENTS,
    INTENT_BAND_DISTRIBUTION,
    INTENT_COLLEGE_SUMMARY,
    INTENT_DEPARTMENT_SUMMARY,
    INTENT_HACKATHON_PERFORMANCE,
    INTENT_POD_PERFORMANCE,
    INTENT_STUDENT_PROFILE,
    INTENT_SCORE_DISTRIBUTION,
    INTENT_UNKNOWN,
]

# LLM model
LLM_MODEL = "gpt-4o-mini"
LLM_TEMPERATURE = 0.0
LLM_MAX_TOKENS = 512