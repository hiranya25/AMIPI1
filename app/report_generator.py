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
from datetime import datetime, timezone
from jinja2 import Environment, FileSystemLoader

from app.config import settings
from app.models import AuditResult

_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")
_env = Environment(loader=FileSystemLoader(_TEMPLATE_DIR))


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def generate(result: AuditResult, diff: dict | None = None) -> dict:
    """Renders + saves the report. Returns paths + the rendered HTML string."""
    os.makedirs(settings.REPORTS_DIR, exist_ok=True)
    ts = _timestamp()

    if diff is None:
        diff = {"has_previous": False, "fixed": [], "new": [], "critical": []}

    template = _env.get_template("report.html")
    html = template.render(
        result=result,
        ai_summary=result.ai_summary or {"executive_summary": "No AI summary available.",
                                          "overall_health_score": "N/A", "top_priorities": []},
        counts=result.issue_counts_by_severity(),
        grouped=result.issues_by_category(),
        diff=diff,
    )

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
        "html": html,
    }
