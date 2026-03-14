# tool.py — TapTap Analytics Chatbot
# ALL_TOOLS and TOOL_MAP are at the BOTTOM — after all function definitions.

from typing import Optional
from langchain_core.tools import tool

import analytics
from logger import logger


# ==============================================================================
# POD TOOLS
# ==============================================================================

@tool
def pod_who_solved_today_tool(college_name: Optional[str] = None) -> list[dict]:
    """Get the list of students who passed today's POD."""
    logger.info(f"[tool] pod_who_solved_today college={college_name}")
    return analytics.get_who_solved_today(college_name=college_name)

@tool
def pod_attempt_count_today_tool(college_name: Optional[str] = None) -> list[dict]:
    """Get the total number of students who attempted today's POD."""
    logger.info(f"[tool] pod_attempt_count_today college={college_name}")
    return analytics.get_attempt_count_today(college_name=college_name)

@tool
def pod_question_today_tool() -> list[dict]:
    """Get today's POD question details."""
    logger.info("[tool] pod_question_today")
    return analytics.get_question_today()

@tool
def pod_fastest_solver_tool(college_name: Optional[str] = None, limit: int = 10) -> list[dict]:
    """Get students who solved today's POD in the fastest time."""
    logger.info(f"[tool] pod_fastest_solver college={college_name} limit={limit}")
    return analytics.get_fastest_solvers(college_name=college_name, limit=limit)

@tool
def pod_not_attempted_today_tool(college_name: Optional[str] = None, limit: int = 20) -> list[dict]:
    """Get students who have NOT attempted today's POD yet."""
    logger.info(f"[tool] pod_not_attempted_today college={college_name}")
    return analytics.get_not_attempted_today(college_name=college_name, limit=limit)

@tool
def pod_pass_fail_summary_tool(
    college_name: Optional[str] = None, date_filter: Optional[str] = None, limit: int = 20
) -> list[dict]:
    """Get pass/fail count per student."""
    logger.info(f"[tool] pod_pass_fail_summary college={college_name} date={date_filter}")
    return analytics.get_pass_fail_summary(college_name=college_name, date_filter=date_filter, limit=limit)

@tool
def pod_pass_rate_tool(college_name: Optional[str] = None) -> list[dict]:
    """Get the overall POD pass rate for a college."""
    logger.info(f"[tool] pod_pass_rate college={college_name}")
    return analytics.get_pass_rate(college_name=college_name)

@tool
def pod_top_passers_tool(college_name: Optional[str] = None, limit: int = 10) -> list[dict]:
    """Get students with the highest number of unique POD questions passed."""
    logger.info(f"[tool] pod_top_passers college={college_name} limit={limit}")
    return analytics.get_top_passers(college_name=college_name, limit=limit)

@tool
def pod_never_passed_tool(college_name: Optional[str] = None, limit: int = 20) -> list[dict]:
    """Get students who have never passed a single POD."""
    logger.info(f"[tool] pod_never_passed college={college_name}")
    return analytics.get_never_passed(college_name=college_name, limit=limit)

@tool
def pod_weekly_passers_tool(college_name: Optional[str] = None, limit: int = 20) -> list[dict]:
    """Get students who passed at least one POD this week."""
    logger.info(f"[tool] pod_weekly_passers college={college_name}")
    return analytics.get_weekly_passers(college_name=college_name, limit=limit)

@tool
def pod_difficulty_breakdown_tool(college_name: Optional[str] = None) -> list[dict]:
    """Get pass rate breakdown by difficulty — easy, medium, hard."""
    logger.info(f"[tool] pod_difficulty_breakdown college={college_name}")
    return analytics.get_difficulty_breakdown(college_name=college_name)

@tool
def pod_language_breakdown_tool(college_name: Optional[str] = None) -> list[dict]:
    """Get breakdown of which programming languages students are using."""
    logger.info(f"[tool] pod_language_breakdown college={college_name}")
    return analytics.get_language_breakdown(college_name=college_name)

@tool
def pod_hard_solvers_tool(college_name: Optional[str] = None, limit: int = 20) -> list[dict]:
    """Get students who successfully solved hard difficulty PODs."""
    logger.info(f"[tool] pod_hard_solvers college={college_name}")
    return analytics.get_hard_solvers(college_name=college_name, limit=limit)

@tool
def pod_longest_streak_tool(college_name: Optional[str] = None, limit: int = 10) -> list[dict]:
    """Get students with the longest POD solving streaks."""
    logger.info(f"[tool] pod_longest_streak college={college_name}")
    return analytics.get_longest_streaks(college_name=college_name, limit=limit)

@tool
def pod_active_streaks_tool(
    college_name: Optional[str] = None, min_streak: int = 3, limit: int = 20
) -> list[dict]:
    """Get students who currently have an active POD streak."""
    logger.info(f"[tool] pod_active_streaks college={college_name} min={min_streak}")
    return analytics.get_active_streaks(college_name=college_name, min_streak=min_streak, limit=limit)

@tool
def pod_lost_streak_tool(college_name: Optional[str] = None, limit: int = 20) -> list[dict]:
    """Get students who recently lost their POD streak."""
    logger.info(f"[tool] pod_lost_streak college={college_name}")
    return analytics.get_lost_streaks(college_name=college_name, limit=limit)

@tool
def pod_top_coins_tool(college_name: Optional[str] = None, limit: int = 10) -> list[dict]:
    """Get students who have earned the most POD coins."""
    logger.info(f"[tool] pod_top_coins college={college_name}")
    return analytics.get_top_coins(college_name=college_name, limit=limit)

@tool
def pod_total_points_today_tool(college_name: Optional[str] = None) -> list[dict]:
    """Get total points earned by students in POD today."""
    logger.info(f"[tool] pod_total_points_today college={college_name}")
    return analytics.get_total_points_today(college_name=college_name)

@tool
def pod_top_scorers_tool(
    college_name: Optional[str] = None,
    limit: int = 10,
    week_filter: Optional[bool] = None,
) -> list[dict]:
    """Get students with the highest total POD score — all time, or this week if week_filter is true."""
    logger.info(f"[tool] pod_top_scorers college={college_name} week={week_filter}")
    return analytics.get_top_scorers(college_name=college_name, limit=limit, week_filter=week_filter)

@tool
def pod_badge_earners_tool(college_name: Optional[str] = None, limit: int = 20) -> list[dict]:
    """Get students who have earned POD badges."""
    logger.info(f"[tool] pod_badge_earners college={college_name}")
    return analytics.get_badge_earners(college_name=college_name, limit=limit)

@tool
def pod_weekly_badge_earners_tool(college_name: Optional[str] = None, limit: int = 20) -> list[dict]:
    """Get students who earned a POD badge this week."""
    logger.info(f"[tool] pod_weekly_badge_earners college={college_name}")
    return analytics.get_weekly_badge_earners(college_name=college_name, limit=limit)

@tool
def pod_student_profile_tool(
    student_name: str,
    college_name: Optional[str] = None,
    date_filter: Optional[str] = None,
    info_type: str = "all",
    language: Optional[str] = None,
    week_filter: Optional[bool] = None,
    pod_type: Optional[str] = None,
) -> dict:
    """Get a student's full POD profile — submissions, streaks, badges, coins."""
    logger.info(f"[tool] pod_student_profile student={student_name} date={date_filter} type={info_type} lang={language} week={week_filter} pod_type={pod_type}")
    return analytics.get_student_profile(
        student_name=student_name, college_name=college_name, date_filter=date_filter,
        info_type=info_type, language=language, week_filter=week_filter, pod_type=pod_type,
    )


# ==============================================================================
# EMPLOYABILITY TOOLS
# ==============================================================================

@tool
def emp_top_scorers_tool(
    college_name: Optional[str] = None,
    limit: int = 10,
    week_filter: Optional[bool] = None,
) -> list[dict]:
    """Get students with the highest total employability score. week_filter=true scopes to this week."""
    logger.info(f"[tool] emp_top_scorers college={college_name} limit={limit} week={week_filter}")
    return analytics.get_emp_top_scorers(college_name=college_name, limit=limit, week_filter=week_filter)

@tool
def emp_difficulty_stats_tool(college_name: Optional[str] = None) -> list[dict]:
    """Get pass rate and submission counts broken down by difficulty — easy, medium, hard."""
    logger.info(f"[tool] emp_difficulty_stats college={college_name}")
    return analytics.get_emp_difficulty_stats(college_name=college_name)

@tool
def emp_language_stats_tool(college_name: Optional[str] = None) -> list[dict]:
    """Get breakdown of programming languages used in employability submissions."""
    logger.info(f"[tool] emp_language_stats college={college_name}")
    return analytics.get_emp_language_stats(college_name=college_name)

@tool
def emp_domain_breakdown_tool(
    college_name: Optional[str] = None,
    domain_name: Optional[str] = None,
) -> list[dict]:
    """Get employability submission counts and pass rates grouped by domain name. Optionally filter to a specific domain."""
    logger.info(f"[tool] emp_domain_breakdown college={college_name} domain={domain_name}")
    return analytics.get_emp_domain_breakdown(college_name=college_name, domain_name=domain_name)

@tool
def emp_subdomain_breakdown_tool(
    college_name: Optional[str] = None, domain_name: Optional[str] = None, limit: int = 20
) -> list[dict]:
    """Get employability submission counts and pass rates grouped by sub-domain topic."""
    logger.info(f"[tool] emp_subdomain_breakdown college={college_name} domain={domain_name}")
    return analytics.get_emp_subdomain_breakdown(college_name=college_name, domain_name=domain_name, limit=limit)

@tool
def emp_question_type_stats_tool(college_name: Optional[str] = None) -> list[dict]:
    """Get employability submission counts and pass rates by question type name."""
    logger.info(f"[tool] emp_question_type_stats college={college_name}")
    return analytics.get_emp_question_type_stats(college_name=college_name)

@tool
def emp_most_solved_tool(college_name: Optional[str] = None, limit: int = 20) -> list[dict]:
    """Get students with the most employability questions marked as solved."""
    logger.info(f"[tool] emp_most_solved college={college_name} limit={limit}")
    return analytics.get_emp_most_solved(college_name=college_name, limit=limit)

@tool
def emp_recent_activity_tool(
    college_name: Optional[str] = None,
    limit: int = 20,
    date_filter: Optional[str] = None,
    days: Optional[int] = None,
    difficulty: Optional[str] = None,
    language: Optional[str] = None,
) -> list[dict]:
    """Get recent employability submissions. Filterable by college, difficulty, language, date, or last N days."""
    logger.info(f"[tool] emp_recent_activity college={college_name} date={date_filter} days={days} difficulty={difficulty} language={language}")
    return analytics.get_emp_recent_activity(
        college_name=college_name, limit=limit, date_filter=date_filter,
        days=days, difficulty=difficulty, language=language,
    )

@tool
def emp_hardest_questions_tool(
    college_name: Optional[str] = None, limit: int = 20, difficulty: Optional[str] = None
) -> list[dict]:
    """Get the employability questions with the lowest pass rate."""
    logger.info(f"[tool] emp_hardest_questions college={college_name} difficulty={difficulty}")
    return analytics.get_emp_hardest_questions(college_name=college_name, limit=limit, difficulty=difficulty)

@tool
def emp_daily_trend_tool(college_name: Optional[str] = None, days: int = 30) -> list[dict]:
    """Get employability submission counts per day over the last N days."""
    logger.info(f"[tool] emp_daily_trend college={college_name} days={days}")
    return analytics.get_emp_daily_trend(college_name=college_name, days=days)

@tool
def emp_pass_rate_tool(college_name: Optional[str] = None) -> list[dict]:
    """Get overall employability pass rate per college."""
    logger.info(f"[tool] emp_pass_rate college={college_name}")
    return analytics.get_emp_pass_rate(college_name=college_name)

@tool
def emp_user_profile_tool(
    student_name: str,
    college_name: Optional[str] = None,
    difficulty: Optional[str] = None,
    language: Optional[str] = None,
    date_filter: Optional[str] = None,
) -> dict:
    """Get a student's full employability profile — summary, submission history, question status."""
    logger.info(f"[tool] emp_user_profile student={student_name} college={college_name} difficulty={difficulty} language={language} date={date_filter}")
    return analytics.get_emp_user_profile(
        student_name=student_name, college_name=college_name,
        difficulty=difficulty, language=language, date_filter=date_filter,
    )


# ==============================================================================
# ASSESS MODULE TOOLS
# ==============================================================================

@tool
def assess_list_tool(assessment_title: Optional[str] = None) -> list[dict]:
    """List all assessments with title, status, open/close time and student counts. Optionally filter by title keyword."""
    logger.info(f"[tool] assess_list title={assessment_title}")
    return analytics.get_assess_list(assessment_title=assessment_title)

@tool
def assess_overview_tool(assessment_title: Optional[str] = None) -> list[dict]:
    """Get overview of a specific assessment — shortlisted, submitted, pass rate, avg score."""
    logger.info(f"[tool] assess_overview title={assessment_title}")
    return analytics.get_assess_overview(assessment_title=assessment_title)

@tool
def assess_student_result_tool(
    student_name: str,
    assessment_title: Optional[str] = None,
) -> list[dict]:
    """Get a student's per-question results for all or a specific assessment."""
    logger.info(f"[tool] assess_student_result student={student_name} title={assessment_title}")
    return analytics.get_assess_student_result(student_name=student_name, assessment_title=assessment_title)

@tool
def assess_top_scorers_tool(
    assessment_title: Optional[str] = None,
    limit: int = 10,
) -> list[dict]:
    """Get top N students by score for a given assessment."""
    logger.info(f"[tool] assess_top_scorers title={assessment_title} limit={limit}")
    return analytics.get_assess_top_scorers(assessment_title=assessment_title, limit=limit)

@tool
def assess_pass_rate_tool(assessment_title: Optional[str] = None) -> list[dict]:
    """Get pass rate per assessment, optionally filtered by title."""
    logger.info(f"[tool] assess_pass_rate title={assessment_title}")
    return analytics.get_assess_pass_rate(assessment_title=assessment_title)

@tool
def assess_skill_breakdown_tool(assessment_title: Optional[str] = None) -> list[dict]:
    """Get pass rate grouped by skill/subdomain for an assessment."""
    logger.info(f"[tool] assess_skill_breakdown title={assessment_title}")
    return analytics.get_assess_skill_breakdown(assessment_title=assessment_title)

@tool
def assess_difficulty_breakdown_tool(assessment_title: Optional[str] = None) -> list[dict]:
    """Get pass rate split by difficulty for an assessment."""
    logger.info(f"[tool] assess_difficulty_breakdown title={assessment_title}")
    return analytics.get_assess_difficulty_breakdown(assessment_title=assessment_title)

@tool
def assess_completion_rate_tool(assessment_title: Optional[str] = None) -> list[dict]:
    """Get completion rate — shortlisted vs submitted vs in-progress for an assessment."""
    logger.info(f"[tool] assess_completion_rate title={assessment_title}")
    return analytics.get_assess_completion_rate(assessment_title=assessment_title)

@tool
def assess_recent_tool(limit: int = 10) -> list[dict]:
    """Get most recently created assessments."""
    logger.info(f"[tool] assess_recent limit={limit}")
    return analytics.get_assess_recent(limit=limit)

@tool
def assess_student_attempts_tool(student_name: str) -> list[dict]:
    """Get attempt history for a student across all assessments."""
    logger.info(f"[tool] assess_student_attempts student={student_name}")
    return analytics.get_assess_student_attempts(student_name=student_name)


# ==============================================================================
# TOOL REGISTRY — must be AFTER all function definitions
# ==============================================================================

ALL_TOOLS = [
    # POD
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
    pod_student_profile_tool,
    # Employability
    emp_top_scorers_tool,
    emp_difficulty_stats_tool,
    emp_language_stats_tool,
    emp_domain_breakdown_tool,
    emp_subdomain_breakdown_tool,
    emp_question_type_stats_tool,
    emp_most_solved_tool,
    emp_recent_activity_tool,
    emp_hardest_questions_tool,
    emp_daily_trend_tool,
    emp_pass_rate_tool,
    emp_user_profile_tool,
    # Assess
    assess_list_tool,
    assess_overview_tool,
    assess_student_result_tool,
    assess_top_scorers_tool,
    assess_pass_rate_tool,
    assess_skill_breakdown_tool,
    assess_difficulty_breakdown_tool,
    assess_completion_rate_tool,
    assess_recent_tool,
    assess_student_attempts_tool,
]

# Dict keyed by tool name — used by llm.py to look up and call tools by name
TOOL_MAP = {t.name: t for t in ALL_TOOLS}