"""
AI Analysis Layer — powered by NVIDIA Nemotron API
(OpenAI-compatible: https://integrate.api.nvidia.com/v1,
 model: nvidia/nemotron-3-ultra-550b-a55b)

Takes the raw list of Issues produced by the audit modules and asks the
model to:
  1. Write a short, plain-English executive summary.
  2. Re-classify / confirm severity (critical / medium / low) per issue.
  3. Produce a prioritized top-N action list with concrete recommendations.

The rest of the pipeline (crawler, audits, report generator, email) works
fine even if this call fails or no API key is set — AI analysis is treated
as an enrichment step, not a hard dependency.
"""
from __future__ import annotations
import json
import logging
import httpx
from openai import OpenAI

from app.config import settings
from app.models import Issue

logger = logging.getLogger("ai_analysis")

SYSTEM_PROMPT = """You are a senior website-health analyst. You will be given a JSON list of
raw technical findings (broken links, SEO/metadata issues, missing ALT tags, performance issues)
from an automated website crawl. Your job:

1. Write a 3-4 sentence plain-English executive summary a non-technical manager can understand.
2. Re-check the severity of each issue category is reasonable (critical / medium / low).
3. Produce a "top_priorities" list of at most 8 items: the highest-impact fixes first, each with
   a one-line recommendation.

Respond ONLY with valid JSON in exactly this shape, no extra commentary:
{
  "executive_summary": "...",
  "overall_health_score": <integer 0-100>,
  "top_priorities": [
    {"issue": "...", "why_it_matters": "...", "recommendation": "..."}
  ]
}
"""


def _client() -> OpenAI | None:
    if not settings.AI_API_KEY:
        logger.warning("AI_API_KEY not set — skipping AI analysis.")
        return None
    # 3-minute timeout so the pipeline never hangs on a slow AI response
    return OpenAI(
        base_url=settings.AI_API_BASE,
        api_key=settings.AI_API_KEY,
        http_client=httpx.Client(timeout=httpx.Timeout(180.0, connect=30.0))
    )


def analyze(issues: list[Issue], site: str, pages_crawled: int) -> dict | None:
    """Calls NVIDIA Nemotron to summarize/prioritize findings.
    Returns a dict (see SYSTEM_PROMPT schema) or falls back to rule-based summary."""
    client = _client()
    if client is None:
        return _fallback_summary(issues, pages_crawled)

    # Keep the payload compact: send counts + a representative sample per category,
    # not every single issue (keeps the request small and fast).
    by_category: dict[str, list[Issue]] = {}
    for issue in issues:
        by_category.setdefault(issue.category, []).append(issue)

    sample_payload = {
        "site": site,
        "pages_crawled": pages_crawled,
        "total_issues": len(issues),
        "categories": {
            cat: {
                "count": len(items),
                "examples": [i.to_dict() for i in items[:5]],
            }
            for cat, items in by_category.items()
        },
    }

    try:
        logger.info("Calling NVIDIA Nemotron API for AI analysis...")
        # Use streaming to handle Nemotron's thinking/reasoning output
        completion = client.chat.completions.create(
            model=settings.AI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(sample_payload)},
            ],
            temperature=0.3,
            top_p=0.9,
            max_tokens=2048,
            stream=True,
        )

        # Collect the streamed response, separating reasoning from content
        content_parts = []
        for chunk in completion:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            # Skip reasoning_content (internal thinking) — we only want the final answer
            if delta.content is not None:
                content_parts.append(delta.content)

        content = "".join(content_parts).strip()
        logger.info("AI analysis response received (%d chars)", len(content))
        # Some models wrap JSON in ```json fences — strip if present.
        content = content.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(content)
    except Exception as exc:  # noqa: BLE001
        logger.error("AI analysis call failed (falling back to rule-based): %s", exc)
        return _fallback_summary(issues, pages_crawled)


def _fallback_summary(issues: list[Issue], pages_crawled: int) -> dict:
    """Rule-based summary used if the AI call is unavailable/fails,
    so the pipeline (and weekly email) never breaks."""
    counts = {"critical": 0, "medium": 0, "low": 0}
    for i in issues:
        counts[i.severity] = counts.get(i.severity, 0) + 1

    score = max(0, 100 - counts["critical"] * 5 - counts["medium"] * 2 - counts["low"] * 1)
    top = sorted(issues, key=lambda i: {"critical": 0, "medium": 1, "low": 2}[i.severity])[:8]

    return {
        "executive_summary": (
            f"Crawled {pages_crawled} pages and found {len(issues)} issues "
            f"({counts['critical']} critical, {counts['medium']} medium, {counts['low']} low). "
            "AI summarization was unavailable for this run, so this is a rule-based summary."
        ),
        "overall_health_score": score,
        "top_priorities": [
            {"issue": i.message, "why_it_matters": i.category, "recommendation": "Review and fix."}
            for i in top
        ],
    }
