# tools.py — TapTap Analytics Chatbot v3
# LangGraph tool wrappers — signatures match analytics.py exactly.

from typing import Optional
from langchain_core.tools import tool

import analytics
from logger import logger


@tool
async def top_students_tool(
    limit: int = 10,
    college_name: Optional[str] = None,
    department: Optional[str] = None,
    band: Optional[str] = None,
) -> list[dict]:
    """Fetch the top N students ranked by employability score.
    Optionally filter by college_name, department, and/or employability band."""
    logger.info(f"[tool] top_students limit={limit} college={college_name} dept={department} band={band}")
    return await analytics.get_top_students(
        limit=limit,
        college_name=college_name,
        department=department,
        band=band,
    )


@tool
async def bottom_students_tool(
    limit: int = 10,
    college_name: Optional[str] = None,
    department: Optional[str] = None,
) -> list[dict]:
    """Fetch the bottom N students with the lowest employability scores.
    Optionally filter by college_name and/or department."""
    logger.info(f"[tool] bottom_students limit={limit} college={college_name} dept={department}")
    return await analytics.get_bottom_students(
        limit=limit,
        college_name=college_name,
        department=department,
    )


@tool
async def band_distribution_tool(
    college_name: Optional[str] = None,
    department: Optional[str] = None,
) -> list[dict]:
    """Get the distribution of students across employability bands (High/Medium/Low/Very Low).
    Optionally filter by college_name and/or department."""
    logger.info(f"[tool] band_distribution college={college_name} dept={department}")
    return await analytics.get_band_distribution(
        college_name=college_name,
        department=department,
    )


@tool
async def college_summary_tool(college_name: Optional[str] = None) -> list[dict]:
    """Get a performance summary for one or all colleges.
    Returns total students, average score, and band breakdowns."""
    logger.info(f"[tool] college_summary college={college_name}")
    return await analytics.get_college_summary(college_name=college_name)


@tool
async def department_summary_tool(
    college_name: Optional[str] = None,
    department: Optional[str] = None,
) -> list[dict]:
    """Get a performance summary per department.
    Optionally filter by college_name and/or a specific department."""
    logger.info(f"[tool] department_summary college={college_name} dept={department}")
    return await analytics.get_department_summary(
        college_name=college_name,
        department=department,
    )


@tool
async def hackathon_performance_tool(
    college_name: Optional[str] = None,
    hackathon_name: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """Fetch student hackathon scores and rankings.
    Optionally filter by college_name and/or hackathon_name."""
    logger.info(f"[tool] hackathon_performance college={college_name} hackathon={hackathon_name} limit={limit}")
    return await analytics.get_hackathon_performance(
        college_name=college_name,
        hackathon_name=hackathon_name,
        limit=limit,
    )


@tool
async def pod_performance_tool(
    college_name: Optional[str] = None,
    department: Optional[str] = None,
    limit: int = 20,
    date_filter: Optional[str] = None,
) -> list[dict]:
    """Fetch pod submission pass/fail counts per student.
    Optionally filter by college_name, department, and/or date_filter.
    date_filter can be 'today' or a date string like '2024-03-09'."""
    logger.info(f"[tool] pod_performance college={college_name} dept={department} limit={limit} date={date_filter}")
    return await analytics.get_pod_performance(
        college_name=college_name,
        department=department,
        limit=limit,
        date_filter=date_filter,
    )


@tool
async def student_profile_tool(
    reg_no: Optional[str] = None,   # FIX: was `str` (required) — now Optional with guard below
    college_name: Optional[str] = None,
) -> list[dict]:
    """Look up a single student's full profile by registration number.
    Optionally scope to a specific college_name for security."""
    logger.info(f"[tool] student_profile reg_no={reg_no} college={college_name}")
    # FIX: guard against missing reg_no (LLM may not always extract it)
    if not reg_no:
        return [{"error": "Please provide a student registration number."}]
    return await analytics.get_student_profile(
        reg_no=reg_no,
        college_name=college_name,
    )


@tool
async def score_distribution_tool(
    college_name: Optional[str] = None,
    department: Optional[str] = None,
    bucket_size: int = 10,
) -> list[dict]:
    """Get a histogram of employability scores grouped into buckets.
    Optionally filter by college_name and/or department."""
    logger.info(f"[tool] score_distribution college={college_name} dept={department} bucket={bucket_size}")
    return await analytics.get_score_distribution(
        college_name=college_name,
        department=department,
        bucket_size=bucket_size,
    )


# ── Tool registry (used by supervisor) ───────────────────────────────────────

ALL_TOOLS = [
    top_students_tool,
    bottom_students_tool,
    band_distribution_tool,
    college_summary_tool,
    department_summary_tool,
    hackathon_performance_tool,
    pod_performance_tool,
    student_profile_tool,
    score_distribution_tool,
]

TOOL_MAP = {t.name: t for t in ALL_TOOLS}