"""
Pipeline Orchestrator
------------------------
Runs the full audit end-to-end:
  crawl -> run all audit modules -> AI analysis -> generate report -> email

This is what both the FastAPI "/audit/run" endpoint and the weekly
scheduler call.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone

from app.audits import alt_tags, broken_links, metadata, performance, seo_checks, security
from app.config import settings
from app.crawler import WebsiteCrawler
from app.audits import comprehensive
from app.detailed_analysis import build as build_detailed_analysis
from app.ai_analysis import analyze
from app.ai_remediation import enrich_issues_with_remediation
from app.report_generator import generate
from app.email_service import send_report
from app.issue_diff import compute_diff, _load_previous_reports
from app.models import AuditResult

logger = logging.getLogger("pipeline")


def run_full_audit(send_email: bool = True) -> AuditResult:
    started_at = datetime.now(timezone.utc).isoformat()
    logger.info("Starting audit for %s", settings.SITE_BASE_URL)

    # 0. Load previous reports BEFORE we overwrite latest.json
    previous_reports = _load_previous_reports()

    # 1. Crawl
    crawler = WebsiteCrawler()
    pages = crawler.crawl()
    logger.info("Crawled %d pages", len(pages))

    # 2. Run all audit modules
    issues = []
    issues += broken_links.run(pages, check_outbound_links=True)
    issues += metadata.run(pages)
    issues += alt_tags.run(pages)
    issues += seo_checks.run(pages, base_url=settings.SITE_BASE_URL)
    issues += performance.run(pages)
    issues += comprehensive.run(pages)
    issues += security.run(pages)

    # 3. Enrich with AI-generated or cached "how to fix" text
    issues = enrich_issues_with_remediation(issues)

    result = AuditResult(
        site=settings.SITE_BASE_URL,
        pages_crawled=len(pages),
        started_at=started_at,
        finished_at=datetime.now(timezone.utc).isoformat(),
        issues=issues,
        stats={
            "avg_response_time_ms": round(
                sum(p.response_time_ms for p in pages) / len(pages), 1
            ) if pages else 0,
            "broken_pages": sum(1 for p in pages if p.status_code and p.status_code >= 400),
        },
    )

    # 3. AI analysis (NVIDIA Nemotron, with rule-based fallback)
    result.ai_summary = analyze(issues, site=settings.SITE_BASE_URL, pages_crawled=len(pages))
    result.analysis, result.page_details = build_detailed_analysis(pages, issues)

    # 4. Compute issue diff (fixed / new / critical)
    issue_dicts = [i.to_dict() for i in issues]
    diff = compute_diff(issue_dicts, previous_reports)

    # 5. Generate report (HTML + JSON, saved to REPORTS_DIR)
    report = generate(result, diff=diff)
    logger.info("Report generated: %s", report["html_path"])

    # 5. Email delivery
    if send_email:
        subject = f"Weekly Website Health Report — {settings.SITE_BASE_URL} ({datetime.now().strftime('%b %d, %Y')})"
        send_report(report["html"], subject=subject)

    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    run_full_audit(send_email=False)
