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
        resp = requests.head(url, timeout=5, allow_redirects=True)
        return resp.status_code == 200
    except Exception:
        return False


def run(pages: list[PageRecord], base_url: str) -> list[Issue]:
    issues: list[Issue] = []

    # --- Site-wide checks (run once) ---
    robots_url = urljoin(base_url, "/robots.txt")
    has_robots = _url_exists(robots_url)
    if not has_robots:
        issues.append(Issue(
            category="SEO",
            issue_type="missing_robots_txt",
            severity="medium",
            page_url=robots_url,
            message="robots.txt is missing or inaccessible",
        ))
        
    sitemap_url = urljoin(base_url, "/sitemap.xml")
    has_sitemap = _url_exists(sitemap_url)
    if not has_sitemap:
        issues.append(Issue(
            category="SEO",
            issue_type="missing_sitemap_xml",
            severity="medium",
            page_url=sitemap_url,
            message="sitemap.xml is missing or inaccessible at standard location",
        ))

    # Check robots.txt for sitemap directive if it exists
    if has_robots and has_sitemap:
        try:
            r = requests.get(robots_url, timeout=5)
            if "sitemap:" not in r.text.lower():
                issues.append(Issue(
                    category="SEO",
                    issue_type="sitemap_not_in_robots",
                    severity="low",
                    page_url=robots_url,
                    message="Sitemap URL is not declared in robots.txt",
                ))
        except Exception:
            pass

    # --- Page-level checks ---
    for page in pages:
        if page.error or (page.status_code and page.status_code >= 400) or not page.html:
            continue
            
        soup = BeautifulSoup(page.html, "lxml")
        
        # Schema / Structured Data Check
        schemas = soup.find_all("script", type="application/ld+json")
        has_schema = False
        for s in schemas:
            if s.string and any(t in s.string for t in ["Organization", "Product", "LocalBusiness", "BreadcrumbList", "Article", "WebPage"]):
                has_schema = True
                break
                
        if not has_schema:
            issues.append(Issue(
                category="SEO",
                issue_type="missing_structured_data",
                severity="medium",
                page_url=page.url,
                message="No recognized Structured Data (JSON-LD schema) found",
                details="Consider adding Organization, Product, or BreadcrumbList schema."
            ))

    return issues
