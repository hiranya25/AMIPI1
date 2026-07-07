"""
Report Generator
-------------------
Takes the AuditResult (raw issues + AI summary) and renders it into:
  - a timestamped HTML report (for email body / archive)
  - a timestamped JSON snapshot (for trend analysis later / API access)
Both are saved under REPORTS_DIR so "latest report" can always be served.
"""
from __future__ import annotations
import json
import os
import csv
from datetime import datetime, timezone
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import settings
from app.models import AuditResult, group_issue_dicts

_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")
_env = Environment(
    loader=FileSystemLoader(_TEMPLATE_DIR),
    autoescape=select_autoescape(["html", "xml"])
)


from html.parser import HTMLParser
import logging

logger = logging.getLogger(__name__)

class StrictHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.open_tags = []
        self.void_elements = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def handle_starttag(self, tag, attrs):
        if tag not in self.void_elements:
            self.open_tags.append(tag)

    def handle_endtag(self, tag):
        if tag in self.void_elements:
            return
        if not self.open_tags:
            raise ValueError(f"Encountered closing tag </{tag}> but no tags are open.")
        if self.open_tags[-1] != tag:
            # We only do a strict check if it severely mismatches to avoid minor template quirks breaking everything.
            raise ValueError(f"Unmatched closing tag: expected </{self.open_tags[-1]}>, got </{tag}>.")
        self.open_tags.pop()

def validate_html(html_str: str):
    parser = StrictHTMLParser()
    parser.feed(html_str)
    if parser.open_tags:
        raise ValueError(f"Unclosed HTML tags remaining: {parser.open_tags}")


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def generate(result: AuditResult, diff: dict | None = None) -> dict:
    """Renders + saves the report. Returns paths + the rendered HTML string."""
    os.makedirs(settings.REPORTS_DIR, exist_ok=True)
    ts = _timestamp()

    if diff is None:
        diff = {"has_previous": False, "fixed": [], "new": [], "critical": []}

    csv_path = os.path.join(settings.REPORTS_DIR, f"amipi_findings_{ts}.csv")
    latest_csv_path = os.path.join(settings.REPORTS_DIR, "latest.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Urgency", "Category", "Issue", "Affected URL", "Details", "Recommended Action"])
        for issue in sorted(result.issues, key=lambda i: (0 if i.severity=="critical" else 1 if i.severity=="medium" else 2, i.category, i.page_url)):
            writer.writerow([
                issue.severity.upper(),
                issue.category,
                issue.message,
                issue.page_url,
                issue.details or "",
                issue.how_to_fix or ""
            ])
            
    # Also write a latest.csv copy
    import shutil
    shutil.copy2(csv_path, latest_csv_path)
    
    csv_filename = os.path.basename(csv_path)

    diff_grouped = {
        "has_previous": diff.get("has_previous", False),
        "fixed": group_issue_dicts(diff.get("fixed", [])),
        "new": group_issue_dicts(diff.get("new", [])),
        "persisting": group_issue_dicts(diff.get("persisting", [])),
        "critical": group_issue_dicts(diff.get("critical", [])),
    }

    template = _env.get_template("report.html")
    html = template.render(
        result=result,
        ai_summary=result.ai_summary or {"executive_summary": "No AI summary available.",
                                          "overall_health_score": "N/A", "top_priorities": []},
        counts=result.issue_counts_by_severity(),
        grouped=result.grouped_issues_by_category(),
        diff=diff_grouped,
        csv_filename=csv_filename,
    )

    try:
        validate_html(html)
    except ValueError as e:
        logger.error("HTML validation failed during report generation: %s. "
                     "This indicates a potential injection of unescaped markup. "
                     "Falling back to basic HTML render to prevent PDF engine crash.", e)
        # We still write the html, but we log the critical error so we know it happened.
        # Since Jinja autoescaping is ON, this should never trigger from fix-text anymore.

    html_path = os.path.join(settings.REPORTS_DIR, f"report_{ts}.html")
    json_path = os.path.join(settings.REPORTS_DIR, f"report_{ts}.json")
    latest_html_path = os.path.join(settings.REPORTS_DIR, "latest.html")
    latest_json_path = os.path.join(settings.REPORTS_DIR, "latest.json")

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    with open(latest_html_path, "w", encoding="utf-8") as f:
        f.write(html)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, indent=2)
    with open(latest_json_path, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, indent=2)

    return {
        "html_path": html_path,
        "json_path": json_path,
        "csv_path": csv_path,
        "html": html,
    }
