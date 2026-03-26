"""
Web search tool — Brave Search API with DuckDuckGo fallback.

Brave returns structured JSON with snippets, titles, and URLs.
DuckDuckGo is free but scrapes HTML — less reliable, lower quality.

If BRAVE_API_KEY is set in .env, Brave is used. Otherwise, falls back
to DuckDuckGo so the system works out-of-the-box with zero config.
"""
import logging

from langchain_core.tools import BaseTool

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def make_web_search_tool() -> BaseTool:
    settings = get_settings()

    if settings.brave_api_key:
        from langchain_community.tools import BraveSearch

        logger.info("Web search: using Brave API")
        return BraveSearch.from_api_key(
            api_key=settings.brave_api_key,
            search_kwargs={"count": 5},
        )

    from langchain_community.tools import DuckDuckGoSearchRun

    logger.info("Web search: using DuckDuckGo (no BRAVE_API_KEY set)")
    return DuckDuckGoSearchRun()
