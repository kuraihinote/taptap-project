# tool.py — TapTap Analytics Chatbot
# 3 broad @tool wrappers replace 44 narrow ones.
# Each accepts a full params dict and delegates to the matching analytics dispatcher.

from langchain_core.tools import tool
import analytics
from logger import logger


@tool
def pod_data_tool(params: dict) -> object:
    """
    Handle ALL POD (Problem of the Day) analytics queries.
    params must include 'query_type' identifying the specific question.
    """
    logger.info(f"[tool] pod_data query_type={params.get('query_type')} params={params}")
    return analytics.get_pod_data(params)


@tool
def emp_data_tool(params: dict) -> object:
    """
    Handle ALL Employability Track analytics queries.
    params must include 'query_type' identifying the specific question.
    """
    logger.info(f"[tool] emp_data query_type={params.get('query_type')} params={params}")
    return analytics.get_emp_data(params)


@tool
def assess_data_tool(params: dict) -> object:
    """
    Handle ALL Assessment analytics queries.
    params must include 'query_type' identifying the specific question.
    """
    logger.info(f"[tool] assess_data query_type={params.get('query_type')} params={params}")
    return analytics.get_assess_data(params)


# ── Tool registry ─────────────────────────────────────────────────────────────

ALL_TOOLS = [pod_data_tool, emp_data_tool, assess_data_tool]

TOOL_MAP = {t.name: t for t in ALL_TOOLS}