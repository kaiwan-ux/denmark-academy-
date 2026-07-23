import logging
from datetime import datetime
from typing import TypedDict

import feedparser
import httpx

from denmark_academy.config import get_settings

logger = logging.getLogger(__name__)


class RSSArticle(TypedDict):
    title: str
    url: str
    source: str
    published_date: datetime | None
    content: str


class RSSFetcher:
    """Fetch latest articles from configured Danish RSS feeds."""

    DEFAULT_RSS_FEEDS = [
        {
            "url": "https://www.dr.dk/nyheder/service/feeds/allenyheder",
            "source": "DR Nyheder",
        },
    ]

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.rss_feeds = self._load_rss_feeds()

    async def fetch_latest_articles(self, max_per_feed: int = 10) -> list[RSSArticle]:
        """Fetch latest articles from all configured RSS feeds and dedupe by URL."""
        all_articles: list[RSSArticle] = []
        seen_urls: set[str] = set()

        for feed_config in self.rss_feeds:
            try:
                articles = await self._fetch_from_feed(
                    feed_config["url"],
                    feed_config["source"],
                    max_per_feed,
                )
                for article in articles:
                    if article["url"] in seen_urls:
                        continue
                    seen_urls.add(article["url"])
                    all_articles.append(article)
                logger.info("Fetched %s articles from %s", len(articles), feed_config["source"])
            except Exception as exc:
                logger.error("Failed to fetch from %s: %s", feed_config["source"], exc)

        return sorted(
            all_articles,
            key=lambda article: article["published_date"] or datetime.min,
            reverse=True,
        )

    async def _fetch_from_feed(
        self,
        feed_url: str,
        source: str,
        max_articles: int,
    ) -> list[RSSArticle]:
        articles: list[RSSArticle] = []
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            response = await client.get(feed_url)
            response.raise_for_status()

        feed = feedparser.parse(response.content)
        for entry in feed.entries[:max_articles]:
            article = self._parse_entry(entry, source)
            if article:
                articles.append(article)
        return articles

    def _parse_entry(self, entry: dict, source: str) -> RSSArticle | None:
        try:
            title = entry.get("title", "").strip()
            url = entry.get("link", "").strip()
            if not title or not url:
                return None

            content = ""
            if hasattr(entry, "summary"):
                content = entry.summary
            elif hasattr(entry, "description"):
                content = entry.description
            elif hasattr(entry, "content") and entry.content:
                content = entry.content[0].value

            published_date = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                published_date = datetime(*entry.published_parsed[:6])
            elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                published_date = datetime(*entry.updated_parsed[:6])

            return RSSArticle(
                title=title,
                url=url,
                source=source,
                published_date=published_date,
                content=content[:5000],
            )
        except Exception as exc:
            logger.warning("Failed to parse RSS entry: %s", exc)
            return None

    def _load_rss_feeds(self) -> list[dict[str, str]]:
        configured = get_settings().current_affairs_rss_feeds.strip()
        if not configured:
            return self.DEFAULT_RSS_FEEDS

        feeds: list[dict[str, str]] = []
        for item in configured.split(","):
            item = item.strip()
            if not item:
                continue
            if "|" in item:
                source, url = item.split("|", 1)
            else:
                source, url = "RSS", item
            source = source.strip()
            url = url.strip()
            if source and url:
                feeds.append({"source": source, "url": url})
        return feeds or self.DEFAULT_RSS_FEEDS
