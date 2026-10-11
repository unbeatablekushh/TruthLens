"""
Search Provider implementations for TruthLens.

Includes:
- SearXNGProvider: Connects to local or remote SearXNG instances.
- DuckDuckGoProvider: Zero-cost HTML web search with URL unquoting and snippet extraction.
- FallbackSearchProvider: Priority-based fallback search provider.
- get_default_search_provider(): Factory returning configured provider.
"""

import httpx
import logging
from typing import List, Optional
from urllib.parse import urlparse, parse_qs, unquote
from bs4 import BeautifulSoup

from app.core.providers import SearchProvider, SearchResult
from app.core.config import settings

logger = logging.getLogger(__name__)


def extract_domain(url: str) -> str:
    """Extract clean domain/host from URL."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


class SearXNGProvider(SearchProvider):
    """
    Local / self-hosted search engine using SearXNG.
    """

    def __init__(self, base_url: Optional[str] = None, timeout: float = 5.0):
        self.base_url = (base_url or getattr(settings, "SEARXNG_BASE_URL", "http://localhost:8080/")).rstrip("/")
        self.timeout = timeout

    async def search(self, query: str, limit: int = 5) -> List[SearchResult]:
        if not query or not query.strip():
            return []

        search_url = f"{self.base_url}/search"
        params = {
            "q": query.strip(),
            "format": "json",
            "language": "en",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(search_url, params=params)

                if response.status_code != 200:
                    logger.warning(f"SearXNG returned status {response.status_code}")
                    return []

                data = response.json()
                raw_results = data.get("results", [])
                results: List[SearchResult] = []

                for item in raw_results[:limit]:
                    url = item.get("url", "").strip()
                    title = item.get("title", "").strip()
                    if not url or not title:
                        continue
                    snippet = item.get("content", "").strip()
                    results.append(
                        SearchResult(
                            title=title,
                            url=url,
                            snippet=snippet,
                            published_date=item.get("publishedDate"),
                            domain=extract_domain(url),
                        )
                    )
                return results

        except httpx.ConnectError:
            logger.info(f"SearXNG instance at {self.base_url} is unreachable.")
            return []
        except httpx.TimeoutException:
            logger.warning(f"SearXNG request timed out after {self.timeout}s.")
            return []
        except Exception as e:
            logger.warning(f"SearXNG search error: {e}")
            return []


class DuckDuckGoProvider(SearchProvider):
    """
    Zero-cost web search using DuckDuckGo HTML endpoint.
    """

    SEARCH_URL = "https://html.duckduckgo.com/html/"
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    def __init__(self, timeout: float = 6.0):
        self.timeout = timeout

    async def search(self, query: str, limit: int = 5) -> List[SearchResult]:
        if not query or not query.strip():
            return []

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                headers=self.HEADERS,
                follow_redirects=True,
            ) as client:
                response = await client.post(self.SEARCH_URL, data={"q": query.strip()})

                if response.status_code != 200:
                    logger.info(f"DuckDuckGo search returned status {response.status_code}")
                    return []

                soup = BeautifulSoup(response.text, "html.parser")
                result_elements = soup.select(".result")
                results: List[SearchResult] = []

                for el in result_elements:
                    if len(results) >= limit:
                        break

                    title_el = el.select_one(".result__title a")
                    snippet_el = el.select_one(".result__snippet")

                    if not title_el:
                        continue

                    title = title_el.get_text(strip=True)
                    raw_href = title_el.get("href", "")

                    # Unquote DuckDuckGo URL redirection wrapper
                    actual_url = raw_href
                    if "uddg=" in raw_href:
                        parsed = parse_qs(urlparse(raw_href).query)
                        uddg_val = parsed.get("uddg")
                        if uddg_val:
                            actual_url = unquote(uddg_val[0])

                    if not actual_url.startswith("http://") and not actual_url.startswith("https://"):
                        continue

                    snippet = snippet_el.get_text(strip=True) if snippet_el else ""

                    results.append(
                        SearchResult(
                            title=title,
                            url=actual_url,
                            snippet=snippet,
                            domain=extract_domain(actual_url),
                        )
                    )

                return results

        except httpx.TimeoutException:
            logger.warning(f"DuckDuckGo search timed out after {self.timeout}s.")
            return []
        except Exception as e:
            logger.warning(f"DuckDuckGo search error: {e}")
            return []


class FallbackSearchProvider(SearchProvider):
    """
    Search provider that chains configured providers in order:
    1. SearXNG
    2. DuckDuckGo
    Returns empty list if neither is available without throwing unhandled errors.
    """

    def __init__(self, providers: Optional[List[SearchProvider]] = None):
        self.providers = providers or [SearXNGProvider(), DuckDuckGoProvider()]

    async def search(self, query: str, limit: int = 5) -> List[SearchResult]:
        for provider in self.providers:
            try:
                results = await provider.search(query, limit=limit)
                if results:
                    return results
            except Exception as e:
                logger.warning(f"Provider {provider.__class__.__name__} failed: {e}")
                continue
        return []


def get_default_search_provider() -> SearchProvider:
    """Factory to get the primary search provider based on configuration."""
    provider_name = getattr(settings, "SEARCH_PROVIDER", "searxng").lower()
    if provider_name == "searxng":
        return FallbackSearchProvider([SearXNGProvider(), DuckDuckGoProvider()])
    elif provider_name == "duckduckgo":
        return FallbackSearchProvider([DuckDuckGoProvider(), SearXNGProvider()])
    return FallbackSearchProvider()
