"""
Issue Diff Engine
-------------------
Compares the current audit's issues against the previous report's issues
to determine:
  - Issues fixed since last run (were in previous, not in current)
  - New issues identified (in current, not in previous)
  - Critical issues requiring attention (all current critical-severity issues)

Issues are fingerprinted by (category, page_url, message) so that
identical findings across runs are matched correctly.
"""
from __future__ import annotations
import json
import os
import glob
import logging
from typing import Optional

from app.config import settings

logger = logging.getLogger("issue_diff")


def _issue_fingerprint(issue: dict) -> str:
    """Create a unique key for an issue based on its core attributes."""
    return f"{issue.get('category', '')}|{issue.get('page_url', '')}|{issue.get('message', '')}"


def _load_previous_report() -> Optional[dict]:
    """Load the most recent previous report JSON (not the current latest)."""
    report_dir = settings.REPORTS_DIR
    pattern = os.path.join(report_dir, "report_*.json")
    files = sorted(glob.glob(pattern), reverse=True)

    # We need the second most recent file (the first is the one we just saved,
    # but during pipeline execution latest.json is the OLD one still)
    # So we load latest.json BEFORE the new report is saved.
    latest_path = os.path.join(report_dir, "latest.json")
    if os.path.exists(latest_path):
        try:
            with open(latest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("issues"):
                logger.info("Loaded previous report for diff comparison (%d issues)", len(data["issues"]))
                return data
        except Exception as exc:
            logger.warning("Could not load previous report: %s", exc)

    return None


def compute_diff(current_issues: list[dict], previous_report: Optional[dict]) -> dict:
    """
    Compare current issues against the previous report.
    
    Returns a dict with:
      - fixed: list of issues that were in previous but not in current
      - new: list of issues that are in current but not in previous
      - critical: list of all current issues with severity == 'critical'
      - has_previous: whether a previous report was available for comparison
    """
    critical = [i for i in current_issues if i.get("severity") == "critical"]

    if previous_report is None:
        return {
            "has_previous": False,
            "fixed": [],
            "new": current_issues,
            "critical": critical,
        }

    prev_issues = previous_report.get("issues", [])
    prev_fingerprints = {_issue_fingerprint(i) for i in prev_issues}
    curr_fingerprints = {_issue_fingerprint(i) for i in current_issues}

    # Fixed = in previous but NOT in current
    fixed = [i for i in prev_issues if _issue_fingerprint(i) not in curr_fingerprints]

    # New = in current but NOT in previous
    new = [i for i in current_issues if _issue_fingerprint(i) not in prev_fingerprints]

    logger.info(
        "Issue diff: %d fixed, %d new, %d critical (prev had %d, current has %d)",
        len(fixed), len(new), len(critical), len(prev_issues), len(current_issues)
    )

    return {
        "has_previous": True,
        "fixed": fixed,
        "new": new,
        "critical": critical,
    }
