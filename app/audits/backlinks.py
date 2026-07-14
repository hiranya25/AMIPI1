"""
Detailed Backlink Analysis.

Fetches optional external backlink data from SE Ranking and normalizes the
provider response into the fields used by the report template.
"""
from __future__ import annotations

import logging

import requests

from app.config import settings

logger = logging.getLogger("backlinks")


def _to_int(value) -> int:
    if value in (None, ""):
        return 0
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _first_present(data: dict, keys: tuple[str, ...]) -> int:
    for key in keys:
        if key in data:
            return _to_int(data[key])
    return 0


def _summary_payload(data) -> dict:
    if not isinstance(data, dict):
        return {}

    summary = data.get("summary")
    if isinstance(summary, list):
        if not summary:
            return {}
        first = summary[0]
        return first if isinstance(first, dict) else {}
    if isinstance(summary, dict):
        return summary

    return data


def _parse_backlink_response(data) -> dict | None:
    summary = _summary_payload(data)
    if not summary:
        return None

    total_backlinks = _first_present(
        summary,
        ("total_backlinks", "backlinks_count", "backlinks"),
    )
    referring_domains = _first_present(
        summary,
        ("referring_domains", "refdomains", "referring_domains_count"),
    )

    return {
        "total_backlinks": total_backlinks,
        "referring_domains": referring_domains,
        "data_source": "SE Ranking",
    }


def fetch_backlink_data(domain: str) -> dict | None:
    api_key = getattr(settings, "SEO_API_KEY", "")

    if not api_key:
        return None

    try:
        url = "https://api.seranking.com/v1/backlinks/summary"
        headers = {
            "Authorization": f"Token {api_key}",
            "Content-Type": "application/json"
        }
        params = {"target": domain}

        resp = requests.get(url, headers=headers, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            backlink_data = _parse_backlink_response(data)
            if backlink_data is None:
                logger.warning("SE Ranking Backlinks API returned an unexpected response shape")
            return backlink_data

        logger.warning("SE Ranking Backlinks API error: %s", resp.status_code)
    except Exception as e:
        logger.error("Failed to fetch backlink data: %s", e)

    return None
