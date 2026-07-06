"""
Shared data structures passed between the crawler, audit modules,
AI analysis layer, and report generator.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PageRecord:
    """A single crawled page, along with the raw data audits need."""
    url: str
    status_code: Optional[int] = None
    content_type: str = ""
    html: str = ""
    response_time_ms: float = 0.0
    size_bytes: int = 0
    depth: int = 0
    redirected_from: Optional[str] = None
    error: Optional[str] = None


@dataclass
class Issue:
    """A single finding produced by an audit module."""
    category: str          # e.g. "Broken Links", "Metadata", "ALT Tags", "SEO", "Performance"
    severity: str           # "critical" | "medium" | "low"  (AI may re-classify later)
    page_url: str
    message: str
    details: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "severity": self.severity,
            "page_url": self.page_url,
            "message": self.message,
            "details": self.details,
        }


@dataclass
class AuditResult:
    """Aggregate result of a full site audit run."""
    site: str
    pages_crawled: int = 0
    started_at: str = ""
    finished_at: str = ""
    issues: list[Issue] = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    ai_summary: Optional[dict] = None
    analysis: dict = field(default_factory=dict)
    page_details: list[dict] = field(default_factory=list)

    def issues_by_category(self) -> dict[str, list[Issue]]:
        grouped: dict[str, list[Issue]] = {}
        for issue in self.issues:
            grouped.setdefault(issue.category, []).append(issue)
        return grouped

    def issue_counts_by_severity(self) -> dict[str, int]:
        counts = {"critical": 0, "medium": 0, "low": 0}
        for issue in self.issues:
            counts[issue.severity] = counts.get(issue.severity, 0) + 1
        return counts

    def to_dict(self) -> dict:
        return {
            "site": self.site,
            "pages_crawled": self.pages_crawled,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "stats": self.stats,
            "issue_counts": self.issue_counts_by_severity(),
            "issues": [i.to_dict() for i in self.issues],
            "ai_summary": self.ai_summary,
            "analysis": self.analysis,
            "page_details": self.page_details,
        }
