"""
Shared data structures passed between the crawler, audit modules,
AI analysis layer, and report generator.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse


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
    issue_type: str        # stable identifier, e.g. "missing_meta_description"
    severity: str           # "critical" | "medium" | "low"  (AI may re-classify later)
    page_url: str
    message: str
    details: Optional[str] = None
    how_to_fix: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "issue_type": self.issue_type,
            "severity": self.severity,
            "page_url": self.page_url,
            "message": self.message,
            "details": self.details,
            "how_to_fix": self.how_to_fix,
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

    def grouped_issues_by_category(self) -> dict[str, list[dict]]:
        """Groups issues by (category, issue_type) and aggregates URL variants."""
        grouped = {}
        for issue in self.issues:
            cat = issue.category
            if cat not in grouped:
                grouped[cat] = {}
            
            # Group by issue type
            itype = issue.issue_type
            if itype not in grouped[cat]:
                grouped[cat][itype] = {
                    "severity": issue.severity,
                    "message": issue.message,
                    "how_to_fix": issue.how_to_fix,
                    "details": issue.details,
                    "base_urls": {} # map of base_url -> set of full urls
                }
            
            # Normalize URL for grouping variants
            parsed = urlparse(issue.page_url)
            base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            
            base_group = grouped[cat][itype]["base_urls"]
            if base_url not in base_group:
                base_group[base_url] = set()
            base_group[base_url].add(issue.page_url)

        # Flatten for the template
        result = {}
        for cat, types in grouped.items():
            result[cat] = []
            for itype, data in types.items():
                total_urls = sum(len(urls) for urls in data["base_urls"].values())
                
                # Take top 5 base URLs as examples
                example_bases = list(data["base_urls"].keys())[:5]
                sample_urls = []
                for base in example_bases:
                    variants = len(data["base_urls"][base])
                    if variants > 1:
                        sample_urls.append(f"{base} (and {variants-1} variant{'s' if variants > 2 else ''})")
                    else:
                        sample_urls.append(base)
                
                result[cat].append({
                    "severity": data["severity"],
                    "message": data["message"],
                    "how_to_fix": data["how_to_fix"],
                    "details": data["details"],
                    "total_affected": total_urls,
                    "sample_urls": sample_urls
                })
        return result

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
