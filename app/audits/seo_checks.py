"""
Technical SEO Checks
----------------------
Site-wide checks that don't apply per-page: robots.txt, XML sitemap,
HTTPS usage, and Schema.org structured data — all flagged in the
SEOptimer audit (XML Sitemaps: X, Schema.org Structured Data: X).
"""
from __future__ import annotations
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from app.config import settings
from app.models import PageRecord, Issue


def _url_exists(url: str) -> bool:
    try:
        resp = requests.get(url, timeout=settings.REQUEST_TIMEOUT,
                             headers={"User-Agent": settings.USER_AGENT})
        return resp.status_code == 200
    except requests.RequestException:
        return False


def run(pages: list[PageRecord], base_url: str | None = None) -> list[Issue]:
    base = (base_url or settings.SITE_BASE_URL).rstrip("/")
    issues: list[Issue] = []

    # --- robots.txt ---
    if not _url_exists(urljoin(base + "/", "robots.txt")):
        issues.append(Issue("SEO", "medium", base, "robots.txt not found"))

    # --- XML sitemap ---
    sitemap_candidates = ["sitemap.xml", "sitemap_index.xml"]
    if not any(_url_exists(urljoin(base + "/", s)) for s in sitemap_candidates):
        issues.append(Issue("SEO", "medium", base, "No XML sitemap detected at common paths"))

    # --- HTTPS ---
    if not base.startswith("https://"):
        issues.append(Issue("SEO", "critical", base, "Site is not served over HTTPS"))

    # --- Schema.org structured data (homepage check) ---
    home = next((p for p in pages if p.url.rstrip("/") == base), pages[0] if pages else None)
    if home and home.html:
        soup = BeautifulSoup(home.html, "lxml")
        has_jsonld = bool(soup.find("script", attrs={"type": "application/ld+json"}))
        has_microdata = bool(soup.find(attrs={"itemtype": True}))
        if not (has_jsonld or has_microdata):
            issues.append(Issue("SEO", "low", home.url, "No Schema.org structured data detected"))

    return issues
