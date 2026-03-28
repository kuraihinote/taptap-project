# tool.py — TapTap Analytics Chatbot (LLM Query Generation approach)
# 3 synchronous @tool wrappers — matching original project pattern.
# POD and Assess return SCHEMA_PENDING until Abdul grants access.

from langchain_core.tools import tool
from logger import logger
import analytics


@tool
def emp_data_tool(question: str) -> dict:
    """Fetch Employability Track analytics by generating SQL from the faculty question."""
    logger.info(f"[tool] emp_data question='{question[:80]}'")
    return analytics.get_emp_data(question)


@tool
def pod_data_tool(question: str) -> dict:
    """Fetch POD analytics by generating SQL from the faculty question."""
    logger.info(f"[tool] pod_data question='{question[:80]}'")
    return analytics.get_pod_data(question)


@tool
def assess_data_tool(question: str) -> dict:
    """Fetch Assessment analytics by generating SQL from the faculty question."""
    logger.info(f"[tool] assess_data question='{question[:80]}'")
    return analytics.get_assess_data(question)


ALL_TOOLS = [emp_data_tool, pod_data_tool, assess_data_tool]
TOOL_MAP  = {t.name: t for t in ALL_TOOLS}