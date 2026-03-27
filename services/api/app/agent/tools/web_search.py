"""
Web search tool — Tavily Search API with DuckDuckGo fallback.

Tavily is purpose-built for AI/RAG: returns clean extracted text
(not raw HTML), relevance scores, and source URLs. Much better
for injecting into an LLM context than raw search engine results.

If TAVILY_API_KEY is set in .env, Tavily is used. Otherwise, falls back
to DuckDuckGo so the system works out-of-the-box with zero config.
"""
import logging

from langchain_core.tools import BaseTool

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def make_web_search_tool() -> BaseTool:
    settings = get_settings()

    if settings.tavily_api_key:
        from langchain_community.tools.tavily_search import TavilySearchResults

        logger.info("Web search: using Tavily API")
        return TavilySearchResults(
            api_key=settings.tavily_api_key,
            max_results=5,
        )

    from langchain_community.tools import DuckDuckGoSearchRun

    logger.info("Web search: using DuckDuckGo (no TAVILY_API_KEY set)")
    return DuckDuckGoSearchRun()
