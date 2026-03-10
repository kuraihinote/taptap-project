# tool.py — TapTap POD Analytics Chatbot
# LangGraph @tool wrappers around analytics.py functions.
# Each tool is a thin pass-through — it just logs and calls the analytics function.

from typing import Optional
from langchain_core.tools import tool

import analytics
from logger import logger


@tool
async def pod_who_solved_today_tool(college_name: Optional[str] = None) -> list[dict]:
    """Get the list of students who passed today's POD."""
    logger.info(f"[tool] pod_who_solved_today college={college_name}")
    return await analytics.get_who_solved_today(college_name=college_name)


@tool
async def pod_attempt_count_today_tool(college_name: Optional[str] = None) -> list[dict]:
    """Get the total number of students who attempted today's POD."""
    logger.info(f"[tool] pod_attempt_count_today college={college_name}")
    return await analytics.get_attempt_count_today(college_name=college_name)


@tool
async def pod_question_today_tool() -> list[dict]:
    """Get today's POD question details — difficulty, type, and attempt count."""
    logger.info("[tool] pod_question_today")
    return await analytics.get_question_today()


@tool
async def pod_fastest_solver_tool(
    college_name: Optional[str] = None,
    limit: int = 10,
) -> list[dict]:
    """Get students who solved today's POD in the fastest time."""
    logger.info(f"[tool] pod_fastest_solver college={college_name} limit={limit}")
    return await analytics.get_fastest_solvers(college_name=college_name, limit=limit)


@tool
async def pod_not_attempted_today_tool(
    college_name: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """Get students who have NOT attempted today's POD yet."""
    logger.info(f"[tool] pod_not_attempted_today college={college_name}")
    return await analytics.get_not_attempted_today(college_name=college_name, limit=limit)


@tool
async def pod_pass_fail_summary_tool(
    college_name: Optional[str] = None,
    date_filter: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """Get pass/fail count per student. date_filter: 'today' or 'YYYY-MM-DD'."""
    logger.info(f"[tool] pod_pass_fail_summary college={college_name} date={date_filter}")
    return await analytics.get_pass_fail_summary(
        college_name=college_name, date_filter=date_filter, limit=limit
    )


@tool
async def pod_pass_rate_tool(college_name: Optional[str] = None) -> list[dict]:
    """Get the overall POD pass rate for a college."""
    logger.info(f"[tool] pod_pass_rate college={college_name}")
    return await analytics.get_pass_rate(college_name=college_name)


@tool
async def pod_top_passers_tool(
    college_name: Optional[str] = None,
    limit: int = 10,
) -> list[dict]:
    """Get students with the highest number of unique POD questions passed."""
    logger.info(f"[tool] pod_top_passers college={college_name} limit={limit}")
    return await analytics.get_top_passers(college_name=college_name, limit=limit)


@tool
async def pod_never_passed_tool(
    college_name: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """Get students who have never passed a single POD."""
    logger.info(f"[tool] pod_never_passed college={college_name}")
    return await analytics.get_never_passed(college_name=college_name, limit=limit)


@tool
async def pod_weekly_passers_tool(
    college_name: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """Get students who passed at least one POD this week."""
    logger.info(f"[tool] pod_weekly_passers college={college_name}")
    return await analytics.get_weekly_passers(college_name=college_name, limit=limit)


@tool
async def pod_difficulty_breakdown_tool(
    college_name: Optional[str] = None,
) -> list[dict]:
    """Get pass rate breakdown by difficulty — easy, medium, hard."""
    logger.info(f"[tool] pod_difficulty_breakdown college={college_name}")
    return await analytics.get_difficulty_breakdown(college_name=college_name)


@tool
async def pod_language_breakdown_tool(
    college_name: Optional[str] = None,
) -> list[dict]:
    """Get breakdown of which programming languages students are using."""
    logger.info(f"[tool] pod_language_breakdown college={college_name}")
    return await analytics.get_language_breakdown(college_name=college_name)


@tool
async def pod_hard_solvers_tool(
    college_name: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """Get students who successfully solved hard difficulty PODs."""
    logger.info(f"[tool] pod_hard_solvers college={college_name}")
    return await analytics.get_hard_solvers(college_name=college_name, limit=limit)


@tool
async def pod_longest_streak_tool(
    college_name: Optional[str] = None,
    limit: int = 10,
) -> list[dict]:
    """Get students with the longest POD solving streaks."""
    logger.info(f"[tool] pod_longest_streak college={college_name}")
    return await analytics.get_longest_streaks(college_name=college_name, limit=limit)


@tool
async def pod_active_streaks_tool(
    college_name: Optional[str] = None,
    min_streak: int = 3,
    limit: int = 20,
) -> list[dict]:
    """Get students who currently have an active POD streak."""
    logger.info(f"[tool] pod_active_streaks college={college_name} min={min_streak}")
    return await analytics.get_active_streaks(
        college_name=college_name, min_streak=min_streak, limit=limit
    )


@tool
async def pod_lost_streak_tool(
    college_name: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """Get students who recently lost their POD streak."""
    logger.info(f"[tool] pod_lost_streak college={college_name}")
    return await analytics.get_lost_streaks(college_name=college_name, limit=limit)


@tool
async def pod_top_coins_tool(
    college_name: Optional[str] = None,
    limit: int = 10,
) -> list[dict]:
    """Get students who have earned the most POD coins."""
    logger.info(f"[tool] pod_top_coins college={college_name}")
    return await analytics.get_top_coins(college_name=college_name, limit=limit)


@tool
async def pod_total_points_today_tool(
    college_name: Optional[str] = None,
) -> list[dict]:
    """Get total points earned by students in POD today."""
    logger.info(f"[tool] pod_total_points_today college={college_name}")
    return await analytics.get_total_points_today(college_name=college_name)


@tool
async def pod_top_scorers_tool(
    college_name: Optional[str] = None,
    limit: int = 10,
) -> list[dict]:
    """Get students with the highest total POD score of all time."""
    logger.info(f"[tool] pod_top_scorers college={college_name}")
    return await analytics.get_top_scorers(college_name=college_name, limit=limit)


@tool
async def pod_badge_earners_tool(
    college_name: Optional[str] = None,
    limit: int = 500,
) -> list[dict]:
    """Get students who have earned POD badges."""
    logger.info(f"[tool] pod_badge_earners college={college_name}")
    return await analytics.get_badge_earners(college_name=college_name, limit=limit)


@tool
async def pod_weekly_badge_earners_tool(
    college_name: Optional[str] = None,
    limit: int = 500,
) -> list[dict]:
    """Get students who earned a POD badge this week."""
    logger.info(f"[tool] pod_weekly_badge_earners college={college_name}")
    return await analytics.get_weekly_badge_earners(college_name=college_name, limit=limit)


# ── Tool registry ─────────────────────────────────────────────────────────────

ALL_TOOLS = [
    pod_who_solved_today_tool,
    pod_attempt_count_today_tool,
    pod_question_today_tool,
    pod_fastest_solver_tool,
    pod_not_attempted_today_tool,
    pod_pass_fail_summary_tool,
    pod_pass_rate_tool,
    pod_top_passers_tool,
    pod_never_passed_tool,
    pod_weekly_passers_tool,
    pod_difficulty_breakdown_tool,
    pod_language_breakdown_tool,
    pod_hard_solvers_tool,
    pod_longest_streak_tool,
    pod_active_streaks_tool,
    pod_lost_streak_tool,
    pod_top_coins_tool,
    pod_total_points_today_tool,
    pod_top_scorers_tool,
    pod_badge_earners_tool,
    pod_weekly_badge_earners_tool,
]

# Dict keyed by tool name — used by llm.py to look up and call tools by name
TOOL_MAP = {t.name: t for t in ALL_TOOLS}