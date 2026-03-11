from langchain_community.tools import DuckDuckGoSearchRun


def make_web_search_tool() -> DuckDuckGoSearchRun:
    """
    Returns a DuckDuckGo search tool.
    Free — no API key required.
    """
    return DuckDuckGoSearchRun()
