"""Tools for Internet Intelligence: live web search, news, and API status."""

from __future__ import annotations

import html
import logging
import re
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Any

from ..schemas import ToolResult
from ..services.api_manager import api_manager
from .registry import tool

logger = logging.getLogger(__name__)

COUNTRY_CODES: dict[str, str] = {
    "india": "in", "indian": "in",
    "usa": "us", "america": "us", "united states": "us", "us": "us",
    "uk": "gb", "britain": "gb", "england": "gb", "united kingdom": "gb",
    "australia": "au", "canada": "ca", "germany": "de", "france": "fr",
    "japan": "jp", "china": "cn", "russia": "ru", "brazil": "br",
    "italy": "it", "spain": "es", "mexico": "mx", "south korea": "kr",
    "korea": "kr", "uae": "ae", "dubai": "ae", "singapore": "sg",
    "pakistan": "pk", "bangladesh": "bd", "netherlands": "nl",
    "sweden": "se", "norway": "no", "switzerland": "ch", "israel": "il",
    "argentina": "ar", "indonesia": "id",
}

NEWSAPI_CATEGORY_MAP: dict[str, str] = {
    "tech": "technology", "ai": "technology", "finance": "business",
    "politics": "general", "gaming": "technology",
    "cybersecurity": "technology", "programming": "technology",
    "startup": "business", "startups": "business",
    "world": "general", "international": "general",
}

GNEWS_CATEGORY_MAP: dict[str, str] = {
    "tech": "technology", "ai": "technology", "finance": "business",
    "politics": "nation", "gaming": "technology",
    "cybersecurity": "technology", "programming": "technology",
    "world": "world", "international": "world",
}

VALID_NEWSAPI_CATEGORIES = {
    "technology", "business", "sports", "entertainment",
    "health", "science", "general",
}

_QUERY_NOISE = re.compile(
    r"\b(related|related to|latest|recent|today|today's|current|new|breaking|live|top|about|on)\b",
    re.IGNORECASE,
)


@tool
def search_web(query: str, max_results: int = 5) -> ToolResult:
    """Search the internet for live information to answer questions.

    :param query: The search query. Keep it concise for better results.
    :param max_results: Maximum number of results to return.
    """
    max_results = max(1, min(int(max_results), 10))
    if api_manager.is_configured("google_cse") and api_manager.settings.google_cse_cx:
        try:
            data = api_manager.get_json(
                "google_cse",
                "https://www.googleapis.com/customsearch/v1",
                params={
                    "key": api_manager.api_key("google_cse"),
                    "cx": api_manager.settings.google_cse_cx,
                    "q": query,
                    "num": max_results,
                },
            )
            results = [
                {
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "body": item.get("snippet", ""),
                    "source": "Google Custom Search",
                }
                for item in data.get("items", [])
            ]
            if results:
                return ToolResult(
                    status="ok",
                    message=f"Found {len(results)} search results.",
                    data={"results": results, "provider": "google_cse"},
                )
        except Exception as e:  # noqa: BLE001
            logger.info("Google CSE failed, falling back to DuckDuckGo: %s", e)

    ddg_error = ""

    # Try ddgs package first (newer, more reliable)
    try:
        from ddgs import DDGS

        results = []
        with DDGS() as ddgs:
            for item in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("href", ""),
                    "body": item.get("body", ""),
                    "source": "DuckDuckGo",
                })

        if results:
            return ToolResult(
                status="ok",
                message=f"Found {len(results)} search results.",
                data={"results": results, "provider": "duckduckgo"},
            )
    except ImportError:
        logger.info("ddgs package is unavailable, trying duckduckgo_search.")
    except Exception as e:  # noqa: BLE001
        ddg_error = str(e)
        logger.info("ddgs search failed: %s. Trying duckduckgo_search.", e)

    # Try the older duckduckgo_search package as secondary
    try:
        from duckduckgo_search import DDGS as DDGSold

        results = []
        with DDGSold() as ddgs:
            for item in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("href", ""),
                    "body": item.get("body", ""),
                    "source": "DuckDuckGo",
                })

        if results:
            return ToolResult(
                status="ok",
                message=f"Found {len(results)} search results.",
                data={"results": results, "provider": "duckduckgo"},
            )
    except ImportError:
        logger.info("duckduckgo_search also unavailable, using HTML fallback.")
    except Exception as e:  # noqa: BLE001
        ddg_error = str(e)
        logger.info("duckduckgo_search also failed: %s. Using HTML fallback.", e)

    try:
        results = _duckduckgo_html_search(query, max_results=max_results)
        if results:
            return ToolResult(
                status="ok",
                message=f"Found {len(results)} search results.",
                data={"results": results, "provider": "duckduckgo_html"},
            )
    except Exception as e:  # noqa: BLE001
        logger.error("DuckDuckGo HTML search failed: %s", e)
        if ddg_error:
            return ToolResult(status="error", message=f"Search failed: {ddg_error}; fallback failed: {e}")
        return ToolResult(status="error", message=f"Search failed: {e}")

    return ToolResult(status="not_found", message=f"No results found for '{query}'.")



@tool
def get_news(
    topic: str = "latest",
    max_results: int = 5,
    category: str = "",
    country: str = "",
    language: str = "",
    provider: str = "auto",
) -> ToolResult:
    """Fetch live news using NewsAPI, GNews, TheNewsAPI, RSS, or DuckDuckGo fallback.

    :param topic: News topic such as latest, AI, finance, cricket, or cybersecurity.
    :param max_results: Maximum number of articles to return.
    :param category: Optional category such as business, technology, sports, health, science, or entertainment.
    :param country: Optional 2-letter country code. Defaults to configured country.
    :param language: Optional 2-letter language code. Defaults to configured language.
    :param provider: auto, newsapi, gnews, thenewsapi, rss, or ddg.
    """
    try:
        articles, used_provider = _fetch_news_articles(
            topic=topic,
            max_results=max_results,
            category=category,
            country=country,
            language=language,
            provider=provider,
        )
        if not articles:
            return ToolResult(status="not_found", message=f"No news found for '{topic}'.")

        return ToolResult(
            status="ok",
            message=f"Found {len(articles)} news articles for {topic}.",
            data={"articles": articles, "provider": used_provider},
        )
    except Exception as e:  # noqa: BLE001
        logger.error("News fetch failed: %s", e)
        return ToolResult(status="error", message=f"News fetch failed: {e}")


@tool
def get_news_briefing(
    topics: str = "world,technology,ai",
    max_per_topic: int = 3,
    provider: str = "auto",
) -> ToolResult:
    """Fetch a multi-topic news briefing for morning, daily, or voice summaries.

    :param topics: Comma-separated topics to include.
    :param max_per_topic: Maximum articles per topic.
    :param provider: auto, newsapi, gnews, thenewsapi, rss, or ddg.
    """
    topic_list = [t.strip() for t in topics.split(",") if t.strip()]
    if not topic_list:
        topic_list = ["world", "technology", "ai"]

    sections: list[dict[str, Any]] = []
    providers_used: set[str] = set()
    for topic in topic_list[:8]:
        try:
            articles, used_provider = _fetch_news_articles(
                topic=topic,
                max_results=max(1, min(int(max_per_topic), 5)),
                provider=provider,
            )
            providers_used.add(used_provider)
            sections.append({"topic": topic, "articles": articles})
        except Exception as exc:  # noqa: BLE001
            sections.append({"topic": topic, "error": str(exc), "articles": []})

    total = sum(len(section.get("articles", [])) for section in sections)
    if total == 0:
        return ToolResult(status="not_found", message="I couldn't fetch any briefing articles.")

    return ToolResult(
        status="ok",
        message=f"Fetched a briefing with {total} articles across {len(sections)} topics.",
        data={"sections": sections, "providers": sorted(providers_used)},
    )


@tool
def get_api_status(provider: str = "all") -> ToolResult:
    """Check which external API providers are configured and their last health state.

    :param provider: all, youtube, google_cse, newsapi, gnews, thenewsapi, or spotify.
    """
    status = api_manager.status()
    key = provider.strip().lower()
    if key != "all":
        status = {key: status.get(key, {"configured": False, "last_status": "unknown"})}
    return ToolResult(status="ok", message="API status loaded.", data={"providers": status})


def _fetch_news_articles(
    *,
    topic: str,
    max_results: int,
    category: str = "",
    country: str = "",
    language: str = "",
    provider: str = "auto",
) -> tuple[list[dict[str, Any]], str]:
    provider = (provider or "auto").strip().lower()
    settings = api_manager.settings
    country = _normalize_country(country or settings.news_default_country or "in")
    language = (language or settings.news_default_language or "en").lower()
    max_results = max(1, min(int(max_results), 20))
    topic = _clean_query(topic)
    category = _normalize_category(category or topic)

    provider_order = _provider_order(provider)
    errors: list[str] = []
    for candidate in provider_order:
        try:
            articles: list[dict[str, Any]] = []
            if candidate == "newsapi":
                articles = _newsapi_articles(topic, max_results, category, country, language)
            elif candidate == "gnews":
                articles = _gnews_articles(topic, max_results, category, country, language)
            elif candidate == "thenewsapi":
                articles = _thenewsapi_articles(topic, max_results, category, country, language)
            elif candidate == "rss":
                articles = _rss_articles(topic, max_results, category, country, language)
            elif candidate == "ddg":
                articles = _ddg_news_articles(topic, max_results)
            articles = _dedup_articles(articles)[:max_results]
            if articles:
                return articles, candidate
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{candidate}: {exc}")
            logger.info("News provider %s failed: %s", candidate, exc)

    raise RuntimeError("; ".join(errors) or "No news providers available.")


def _provider_order(provider: str) -> list[str]:
    if provider in {"newsapi", "gnews", "thenewsapi", "rss", "ddg"}:
        return [provider, "rss"] if provider != "rss" else ["rss"]

    order: list[str] = []
    if api_manager.is_configured("newsapi"):
        order.append("newsapi")
    if api_manager.is_configured("gnews"):
        order.append("gnews")
    if api_manager.is_configured("thenewsapi"):
        order.append("thenewsapi")
    order.append("rss")
    order.append("ddg")
    return order


def _newsapi_articles(
    topic: str,
    max_results: int,
    category: str,
    country: str,
    language: str,
) -> list[dict[str, Any]]:
    key = api_manager.api_key("newsapi")
    if not key:
        raise RuntimeError("NEWS_API_KEY is not configured.")

    mapped_category = NEWSAPI_CATEGORY_MAP.get(category, category)
    if mapped_category not in VALID_NEWSAPI_CATEGORIES:
        mapped_category = ""

    is_headlines = _is_latest(topic) or bool(mapped_category)
    if is_headlines:
        url = "https://newsapi.org/v2/top-headlines"
        params = {
            "apiKey": key,
            "pageSize": max_results,
            "country": country,
            "category": mapped_category,
            "q": "" if _is_latest(topic) else topic,
        }
    else:
        url = "https://newsapi.org/v2/everything"
        params = {
            "apiKey": key,
            "pageSize": max_results,
            "q": topic,
            "language": language,
            "sortBy": "publishedAt",
        }

    data = api_manager.get_json("newsapi", url, params=params)
    if data.get("status") not in (None, "ok"):
        raise RuntimeError(data.get("message") or "NewsAPI returned an error.")
    return [_normalize_article(a, "NewsAPI") for a in data.get("articles", [])[:max_results]]


def _gnews_articles(
    topic: str,
    max_results: int,
    category: str,
    country: str,
    language: str,
) -> list[dict[str, Any]]:
    key = api_manager.api_key("gnews")
    if not key:
        raise RuntimeError("GNEWS_API_KEY is not configured.")

    mapped_category = GNEWS_CATEGORY_MAP.get(category, category)
    if _is_latest(topic) or mapped_category:
        url = "https://gnews.io/api/v4/top-headlines"
        params = {
            "apikey": key,
            "max": max_results,
            "country": country,
            "lang": language,
            "category": mapped_category or None,
        }
    else:
        url = "https://gnews.io/api/v4/search"
        params = {
            "apikey": key,
            "max": max_results,
            "country": country,
            "lang": language,
            "q": topic,
        }

    data = api_manager.get_json("gnews", url, params=params)
    if data.get("errors"):
        raise RuntimeError(str(data["errors"]))
    return [_normalize_article(a, "GNews") for a in data.get("articles", [])[:max_results]]


def _thenewsapi_articles(
    topic: str,
    max_results: int,
    category: str,
    country: str,
    language: str,
) -> list[dict[str, Any]]:
    key = api_manager.api_key("thenewsapi")
    if not key:
        raise RuntimeError("THENEWSAPI_KEY is not configured.")

    params = {
        "api_token": key,
        "limit": max_results,
        "language": language,
        "locale": country,
    }
    if not _is_latest(topic):
        params["search"] = topic
    if category and not _is_latest(category):
        params["categories"] = category

    data = api_manager.get_json(
        "thenewsapi",
        "https://api.thenewsapi.com/v1/news/top",
        params=params,
    )
    return [_normalize_article(a, "TheNewsAPI") for a in data.get("data", [])[:max_results]]


def _rss_articles(
    topic: str,
    max_results: int,
    category: str,
    country: str,
    language: str,
) -> list[dict[str, Any]]:
    query = "top news" if _is_latest(topic) else topic
    if category:
        query = f"{category} {query}"
    q = urllib.parse.quote(query)
    ceid = f"{country.upper()}:{language}"
    url = f"https://news.google.com/rss/search?q={q}&hl={language}-{country.upper()}&gl={country.upper()}&ceid={ceid}"

    xml_text = api_manager.get_text("rss", url, headers={"User-Agent": "Genie/1.0"})
    root = ET.fromstring(xml_text)

    results: list[dict[str, Any]] = []
    for item in root.findall(".//item")[:max_results]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = _strip_html(item.findtext("description") or "")
        published_at = (item.findtext("pubDate") or "").strip()
        src_el = item.find("{https://news.google.com/rss}source")
        source = src_el.text.strip() if src_el is not None and src_el.text else "Google News"
        if title and link:
            results.append({
                "title": html.unescape(title),
                "source": source,
                "description": desc[:300],
                "url": link,
                "published_at": published_at,
                "provider": "Google News RSS",
            })
    return results


def _ddg_news_articles(topic: str, max_results: int) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    try:
        from ddgs import DDGS

        with DDGS() as ddgs:
            for item in ddgs.news(topic, max_results=max_results):
                results.append({
                    "title": item.get("title", ""),
                    "source": item.get("source") or "DuckDuckGo News",
                    "description": item.get("body") or item.get("excerpt") or "",
                    "url": item.get("url") or "",
                    "image_url": item.get("image") or "",
                    "published_at": item.get("date") or "",
                    "provider": "DuckDuckGo News",
                })
        if results:
            return _dedup_articles(results)[:max_results]
    except Exception as exc:  # noqa: BLE001
        logger.info("DuckDuckGo news endpoint failed: %s", exc)

    try:
        fallback_results = _duckduckgo_html_search(f"{topic} news", max_results=max_results)
        return [
            {
                "title": item.get("title", ""),
                "source": item.get("source") or "DuckDuckGo Search",
                "description": item.get("body", ""),
                "url": item.get("url", ""),
                "image_url": "",
                "published_at": "",
                "provider": "DuckDuckGo Search",
            }
            for item in fallback_results
        ]
    except Exception as exc:  # noqa: BLE001
        logger.info("DuckDuckGo news search fallback failed: %s", exc)
        return []


def _duckduckgo_html_search(query: str, max_results: int) -> list[dict[str, Any]]:
    url = "https://html.duckduckgo.com/html/"
    html_text = api_manager.get_text(
        "duckduckgo",
        url,
        params={"q": query},
        headers={"User-Agent": "Genie/1.0"},
    )
    return _parse_duckduckgo_html_results(html_text, max_results=max_results)


def _parse_duckduckgo_html_results(html_text: str, max_results: int) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    link_re = re.compile(
        r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    matches = list(link_re.finditer(html_text or ""))
    for index, match in enumerate(matches):
        href = _decode_duckduckgo_url(html.unescape(match.group(1)))
        title = _strip_html(match.group(2))
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else start + 1200
        block = html_text[start:end]
        snippet_match = re.search(
            r'class="[^"]*result__snippet[^"]*"[^>]*>(.*?)<(?:/div|/a)>',
            block,
            re.IGNORECASE | re.DOTALL,
        )
        body = _strip_html(snippet_match.group(1)) if snippet_match else ""
        if title and href:
            results.append({
                "title": title,
                "url": href,
                "body": body,
                "source": _source_from_url(href),
            })
        if len(results) >= max_results:
            break
    return results


def _decode_duckduckgo_url(url: str) -> str:
    raw = (url or "").strip()
    if raw.startswith("//"):
        raw = "https:" + raw
    elif raw.startswith("/"):
        raw = "https://duckduckgo.com" + raw

    parsed = urllib.parse.urlparse(raw)
    params = urllib.parse.parse_qs(parsed.query)
    if params.get("uddg"):
        return urllib.parse.unquote(params["uddg"][0])
    return raw


def _source_from_url(url: str) -> str:
    host = urllib.parse.urlparse(url).hostname or ""
    return host.removeprefix("www.") or "Web"


def _normalize_article(article: dict[str, Any], provider: str) -> dict[str, Any]:
    source = article.get("source") or {}
    if isinstance(source, dict):
        source_name = source.get("name") or provider
    else:
        source_name = str(source or provider)

    return {
        "title": html.unescape(str(article.get("title") or "")),
        "source": source_name,
        "author": article.get("author") or "",
        "description": _strip_html(article.get("description") or article.get("content") or "")[:300],
        "url": article.get("url") or "",
        "image_url": article.get("urlToImage") or article.get("image") or "",
        "published_at": article.get("publishedAt") or article.get("published_at") or "",
        "provider": provider,
    }


def _normalize_country(value: str) -> str:
    raw = (value or "").strip().lower()
    if len(raw) == 2:
        return raw
    return COUNTRY_CODES.get(raw, raw or "in")


def _normalize_category(value: str) -> str:
    raw = (value or "").strip().lower()
    raw = NEWSAPI_CATEGORY_MAP.get(raw, raw)
    return raw if raw in VALID_NEWSAPI_CATEGORIES else ""


def _clean_query(raw: str) -> str:
    cleaned = _QUERY_NOISE.sub("", raw or "").strip()
    cleaned = " ".join(cleaned.split())
    return cleaned or raw or "latest"


def _dedup_articles(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for article in articles:
        title = (article.get("title") or "").strip()
        url = (article.get("url") or "").strip()
        key = url or title
        if not title or title == "[Removed]" or key in seen:
            continue
        seen.add(key)
        out.append(article)
    return out


def _is_latest(topic: str) -> bool:
    return (topic or "").strip().lower() in {"", "latest", "top", "headlines", "breaking", "today"}


def _strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", "", value or "")
    return html.unescape(re.sub(r"\s+", " ", text)).strip()
