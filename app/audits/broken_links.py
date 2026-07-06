"""
Broken Link Checker
--------------------
Flags any crawled page that returned a 4xx/5xx status, plus any
outbound <a href> link (internal or external) that resolves to an error.
Mirrors the '404' rows seen repeatedly in the GTmetrix waterfall
(e.g. product_thumb.php?... returning 404).
"""
from __future__ import annotations
import requests
from bs4 import BeautifulSoup

from app.config import settings
from app.models import PageRecord, Issue

_checked_cache: dict[str, int | None] = {}


def _check_status(url: str) -> int | None:
    if url in _checked_cache:
        return _checked_cache[url]
    try:
        resp = requests.head(
            url, timeout=settings.REQUEST_TIMEOUT, allow_redirects=True,
            headers={"User-Agent": settings.USER_AGENT},
        )
        # Some servers reject HEAD; fall back to GET.
        if resp.status_code >= 400:
            resp = requests.get(
                url, timeout=settings.REQUEST_TIMEOUT, allow_redirects=True,
                headers={"User-Agent": settings.USER_AGENT}, stream=True,
            )
        _checked_cache[url] = resp.status_code
        return resp.status_code
    except requests.RequestException:
        _checked_cache[url] = None
        return None


def run(pages: list[PageRecord], check_outbound_links: bool = True) -> list[Issue]:
    issues: list[Issue] = []

    # 1. Pages that themselves failed to load.
    for page in pages:
        if page.error:
            issues.append(Issue(
                category="Broken Links",
                severity="critical",
                page_url=page.url,
                message="Page failed to load",
                details=page.error,
            ))
        elif page.status_code and page.status_code >= 400:
            issues.append(Issue(
                category="Broken Links",
                severity="critical" if page.status_code >= 500 else "medium",
                page_url=page.url,
                message=f"Page returned HTTP {page.status_code}",
            ))

    # 2. Links referenced on each page (checked with HEAD/GET, deduplicated via cache).
    if check_outbound_links:
        for page in pages:
            if not page.html:
                continue
            soup = BeautifulSoup(page.html, "lxml")
            for tag, attr in (("a", "href"), ("img", "src"), ("script", "src"), ("link", "href")):
                for el in soup.find_all(tag, **{attr: True}):
                    target = el[attr].strip()
                    if not target or target.startswith(("mailto:", "tel:", "javascript:", "#", "data:")):
                        continue
                    if not target.startswith("http"):
                        continue  # normalization/dedup for relative URLs is handled by the crawler pass
                    status = _check_status(target)
                    if status is None or status >= 400:
                        issues.append(Issue(
                            category="Broken Links",
                            severity="medium",
                            page_url=page.url,
                            message=f"Broken resource ({tag}): {'no response' if status is None else f'HTTP {status}'}",
                            details=target,
                        ))
    return issues
