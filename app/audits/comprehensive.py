"""Additional checks used by the detailed management report."""
from __future__ import annotations

import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from app.models import Issue, PageRecord


def run(pages: list[PageRecord]) -> list[Issue]:
    issues: list[Issue] = []
    for page in pages:
        if not page.html or page.error or (page.status_code and page.status_code >= 400):
            continue
        soup = BeautifulSoup(page.html, "lxml")

        # Social discovery metadata
        if not soup.find("meta", attrs={"property": "og:title"}):
            issues.append(Issue("Social Metadata", "low", page.url, "Missing Open Graph title", "Add og:title for reliable social previews."))
        if not soup.find("meta", attrs={"property": "og:description"}):
            issues.append(Issue("Social Metadata", "low", page.url, "Missing Open Graph description", "Add og:description using the page's unique value proposition."))
        if not soup.find("meta", attrs={"name": re.compile(r"^twitter:card$", re.I)}):
            issues.append(Issue("Social Metadata", "low", page.url, "Missing Twitter/X card metadata", "Add twitter:card and related sharing tags."))

        # Accessibility fundamentals visible in static markup
        html_tag = soup.find("html")
        if not html_tag or not html_tag.get("lang"):
            issues.append(Issue("Accessibility", "medium", page.url, "Document language is not declared", "Add a valid lang attribute to <html>."))
        unnamed = [a for a in soup.find_all("a") if not a.get_text(" ", strip=True) and not a.get("aria-label") and not a.find("img", alt=True)]
        if unnamed:
            issues.append(Issue("Accessibility", "medium", page.url, f"{len(unnamed)} links have no accessible name", "Add visible link text or an aria-label."))
        form_controls = soup.find_all(["input", "select", "textarea"])
        unlabeled = []
        for control in form_controls:
            if control.name == "input" and control.get("type", "text").lower() in {"hidden", "submit", "button", "image"}:
                continue
            cid = control.get("id")
            if not control.get("aria-label") and not control.get("aria-labelledby") and not (cid and soup.find("label", attrs={"for": cid})):
                unlabeled.append(control)
        if unlabeled:
            issues.append(Issue("Accessibility", "medium", page.url, f"{len(unlabeled)} form controls lack labels", "Associate each control with a label or aria-label."))

        # Content quality signals
        main = soup.find("main") or soup.find("body") or soup
        words = len(re.findall(r"\b[\w'-]+\b", main.get_text(" ", strip=True)))
        if words < 150:
            issues.append(Issue("Content", "medium", page.url, f"Thin page content: approximately {words} words", "Add useful, intent-focused copy, FAQs, and internal links."))
        if not soup.find_all("h2"):
            issues.append(Issue("Content", "low", page.url, "No H2 subheadings found", "Organize the page with descriptive H2 sections."))

        # URL consistency
        parsed = urlparse(page.url)
        if "//" in parsed.path:
            issues.append(Issue("URL Structure", "medium", page.url, "URL contains repeated slashes", "Redirect to one normalized URL and update internal links."))
        if any(ch.isupper() for ch in parsed.path):
            issues.append(Issue("URL Structure", "low", page.url, "URL contains uppercase characters", "Use lowercase canonical URLs consistently."))

        # Browser security policy signals (markup-level; headers are collected separately later)
        if soup.find(src=re.compile(r"^http://", re.I)) or soup.find(href=re.compile(r"^http://", re.I)):
            issues.append(Issue("Security", "critical", page.url, "HTTP resource referenced from an HTTPS page", "Serve every asset over HTTPS and remove mixed-content references."))
    return issues
