"""
Website crawler.

Performs a breadth-first crawl of every internal page reachable from
SITE_BASE_URL (up to MAX_PAGES), collecting the raw HTML, status code,
response time, and payload size that every audit module needs.

Two fetch strategies:
  - requests + BeautifulSoup (fast, default) for static HTML.
  - Playwright (optional, USE_PLAYWRIGHT_FOR_JS=true) for JS-rendered pages,
    since amipi.com's PageSpeed report shows heavy client-side JS.
"""
from __future__ import annotations
import time
import logging
from collections import deque
from urllib.parse import urljoin, urlparse, urldefrag

import requests
from bs4 import BeautifulSoup
import tldextract

from app.config import settings
from app.models import PageRecord

logger = logging.getLogger("crawler")


def _same_registered_domain(url_a: str, url_b: str) -> bool:
    a = tldextract.extract(url_a)
    b = tldextract.extract(url_b)
    return (a.domain, a.suffix) == (b.domain, b.suffix)


def _normalize(base: str, link: str) -> str | None:
    if not link:
        return None
    link = link.strip()
    if link.startswith(("mailto:", "tel:", "javascript:", "#")):
        return None
    absolute = urljoin(base, link)
    absolute, _ = urldefrag(absolute)  # strip #fragments
    parsed = urlparse(absolute)
    if parsed.scheme not in ("http", "https"):
        return None
    return absolute


class WebsiteCrawler:
    def __init__(self, base_url: str | None = None, max_pages: int | None = None):
        self.base_url = (base_url or settings.SITE_BASE_URL).rstrip("/")
        self.max_pages = max_pages or settings.MAX_PAGES
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": settings.USER_AGENT})
        self._playwright_ctx = None  # lazily initialized

    # ---------------------------------------------------------------- fetch
    def _fetch_with_requests(self, url: str) -> PageRecord:
        start = time.perf_counter()
        try:
            resp = self.session.get(
                url, timeout=settings.REQUEST_TIMEOUT, allow_redirects=True
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            return PageRecord(
                url=url,
                status_code=resp.status_code,
                content_type=resp.headers.get("Content-Type", ""),
                html=resp.text if "text/html" in resp.headers.get("Content-Type", "") else "",
                response_time_ms=round(elapsed_ms, 1),
                size_bytes=len(resp.content),
                redirected_from=url if resp.url != url else None,
            )
        except requests.RequestException as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return PageRecord(
                url=url,
                status_code=None,
                response_time_ms=round(elapsed_ms, 1),
                error=str(exc),
            )

    def _fetch_with_playwright(self, url: str) -> PageRecord:
        # Imported lazily so `playwright` is only required if this mode is used.
        from playwright.sync_api import sync_playwright

        start = time.perf_counter()
        try:
            if self._playwright_ctx is None:
                self._pw = sync_playwright().start()
                self._browser = self._pw.chromium.launch(headless=True)
                self._playwright_ctx = self._browser.new_context(
                    user_agent=settings.USER_AGENT
                )
            page = self._playwright_ctx.new_page()
            response = page.goto(url, wait_until="networkidle", timeout=settings.REQUEST_TIMEOUT * 1000)
            html = page.content()
            status = response.status if response else None
            elapsed_ms = (time.perf_counter() - start) * 1000
            page.close()
            return PageRecord(
                url=url,
                status_code=status,
                content_type="text/html",
                html=html,
                response_time_ms=round(elapsed_ms, 1),
                size_bytes=len(html.encode("utf-8")),
            )
        except Exception as exc:  # noqa: BLE001 - want to record any failure per-page
            elapsed_ms = (time.perf_counter() - start) * 1000
            return PageRecord(url=url, response_time_ms=round(elapsed_ms, 1), error=str(exc))

    def _fetch(self, url: str) -> PageRecord:
        if settings.USE_PLAYWRIGHT_FOR_JS:
            return self._fetch_with_playwright(url)
        return self._fetch_with_requests(url)

    def close(self):
        if self._playwright_ctx is not None:
            self._browser.close()
            self._pw.stop()

    # ---------------------------------------------------------------- crawl
    def crawl(self) -> list[PageRecord]:
        """BFS crawl starting at base_url. Returns a list of PageRecords
        (only internal, same-registered-domain pages are followed)."""
        visited: set[str] = set()
        queue: deque[tuple[str, int]] = deque([(self.base_url, 0)])
        pages: list[PageRecord] = []

        while queue and len(visited) < self.max_pages:
            url, depth = queue.popleft()
            if url in visited:
                continue
            visited.add(url)

            record = self._fetch(url)
            record.depth = depth
            pages.append(record)
            logger.info("Crawled [%s] %s (%sms)", record.status_code, url, record.response_time_ms)

            time.sleep(settings.CRAWL_DELAY_SECONDS)

            if not record.html:
                continue

            for href in self._extract_links(record.html, url):
                if href not in visited and _same_registered_domain(href, self.base_url):
                    queue.append((href, depth + 1))

        self.close()
        return pages

    @staticmethod
    def _extract_links(html: str, page_url: str) -> list[str]:
        soup = BeautifulSoup(html, "lxml")
        links = []
        for a in soup.find_all("a", href=True):
            normalized = _normalize(page_url, a["href"])
            if normalized:
                links.append(normalized)
        return links
