import json
import logging
import os
import time
import hashlib
from typing import Optional
from dataclasses import replace

import httpx
from openai import OpenAI

from app.config import settings
from app.models import Issue

logger = logging.getLogger("ai_remediation")

CACHE_FILE = os.path.join(settings.REPORTS_DIR, "remediation_cache.json")
# 30 days TTL (in seconds)
CACHE_TTL = 30 * 24 * 60 * 60

STATIC_FALLBACKS = {
    "missing_title": "Ensure every HTML page has a <title> tag within the <head> block.",
    "title_length_incorrect": "Rewrite the title to be between 50 and 60 characters for optimal search engine display.",
    "missing_meta_description": "Add a <meta name=\"description\" content=\"...\"> tag summarizing the page's value proposition.",
    "meta_desc_length": "Adjust the meta description to be between 120 and 160 characters.",
    "missing_canonical_tag": "Add a <link rel=\"canonical\" href=\"...\"> tag pointing to the preferred URL for this page.",
    "missing_lang_attribute": "Add a lang attribute to the root HTML element (e.g., <html lang=\"en\">).",
    "missing_h1_tag": "Add exactly one descriptive <h1> tag to the page.",
    "multiple_h1_tags": "Ensure there is only one <h1> tag; use <h2> for other major headings.",
    "broken_internal_link": "Fix the link to point to a valid page or remove it if the destination no longer exists.",
    "broken_external_link": "Update the external link to a valid URL or remove it.",
    "missing_alt_attribute": "Add an alt attribute to the image describing its contents.",
    "all_images_missing_alt": "Add descriptive alt attributes to all images on the page.",
    "slow_response_time": "Optimize server response time. Consider caching, database optimization, or CDN usage.",
    "large_payload_size": "Reduce page size by compressing images, minifying CSS/JS, and enabling GZIP/Brotli.",
    "render_blocking_scripts": "Add 'async' or 'defer' to script tags or move them to the bottom of the body.",
    "high_resource_count": "Combine CSS/JS files and use CSS sprites or icon fonts to reduce total HTTP requests.",
    "missing_robots_txt": "Create a robots.txt file at the root of the domain.",
    "missing_sitemap_xml": "Generate an XML sitemap and place it at /sitemap.xml.",
    "sitemap_not_in_robots": "Add a 'Sitemap: URL' directive to your robots.txt.",
    "missing_structured_data": "Implement JSON-LD Schema.org markup relevant to the page content.",
    "mixed_content": "Update all HTTP resource URLs (images, scripts, styles) to HTTPS.",
    "missing_security_headers": "Configure the web server to emit HSTS, X-Content-Type-Options, and X-Frame-Options headers.",
}


def _load_cache() -> dict:
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
            now = time.time()
            # Clean expired items
            valid_cache = {k: v for k, v in cache.items() if (now - v.get("ts", 0)) < CACHE_TTL}
            return valid_cache
    except Exception:
        return {}


def _save_cache(cache: dict):
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
    except Exception as exc:
        logger.warning("Failed to save remediation cache: %s", exc)


def _generate_ai_fix(issue_type: str, category: str, sample_messages: list[str]) -> Optional[str]:
    if not settings.AI_API_KEY:
        return None

    client = OpenAI(
        base_url=settings.AI_API_BASE,
        api_key=settings.AI_API_KEY,
        http_client=httpx.Client(timeout=httpx.Timeout(60.0))
    )

    prompt = f"""You are a technical web expert.
Provide a concise, 1-2 sentence actionable fix for the following website issue type.
Category: {category}
Issue Type: {issue_type}
Sample Error Messages seen on the site:
{chr(10).join(f"- {msg}" for msg in sample_messages)}

Provide ONLY the recommended fix text, nothing else. No markdown formatting or quotes.
"""
    for attempt in range(3):
        try:
            completion = client.chat.completions.create(
                model=settings.AI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=256,
            )
            fix_text = completion.choices[0].message.content.strip()
            # Strip quotes if the model added them
            if fix_text.startswith('"') and fix_text.endswith('"'):
                fix_text = fix_text[1:-1]
            return fix_text
        except Exception as exc:
            if attempt < 2:
                time.sleep(2 ** attempt)
            else:
                logger.error("AI fix generation failed for %s: %s", issue_type, exc)
                return None


def enrich_issues_with_remediation(issues: list[Issue]) -> list[Issue]:
    cache = _load_cache()
    updated_cache = False

    # Group by issue_type
    by_type: dict[str, list[Issue]] = {}
    for issue in issues:
        by_type.setdefault(issue.issue_type, []).append(issue)

    type_to_fix: dict[str, str] = {}

    for issue_type, group in by_type.items():
        # Hash context to see if we need a new fix (issue_type + category is enough for this app)
        category = group[0].category
        cache_key = f"{issue_type}_{category}"

        if cache_key in cache:
            type_to_fix[issue_type] = cache[cache_key]["fix"]
            logger.debug("Cache hit for remediation: %s", issue_type)
        else:
            # Get unique messages for context
            messages = list({i.message for i in group})[:3]
            ai_fix = _generate_ai_fix(issue_type, category, messages)
            
            if ai_fix:
                type_to_fix[issue_type] = ai_fix
                cache[cache_key] = {"fix": ai_fix, "ts": time.time()}
                updated_cache = True
                logger.info("AI generated fix for %s", issue_type)
            else:
                # Fallback
                fallback = STATIC_FALLBACKS.get(issue_type, "Review and resolve the issue.")
                type_to_fix[issue_type] = fallback
                logger.info("Using static fallback fix for %s", issue_type)

    if updated_cache:
        _save_cache(cache)

    # Reconstruct issues using dataclasses.replace as requested
    enriched = []
    for issue in issues:
        fix_text = type_to_fix.get(issue.issue_type, "Review and resolve.")
        
        # For critical issues, optionally append details context
        if issue.severity == "critical" and issue.details:
            fix_text = f"{fix_text} (Context: {issue.details})"
            
        new_issue = replace(issue, how_to_fix=fix_text)
        enriched.append(new_issue)

    return enriched
