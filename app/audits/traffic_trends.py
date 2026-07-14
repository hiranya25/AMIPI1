"""
Organic Traffic & Ranking Trends (Stub)
---------------------------------------
Checks for an external API key. If not present, returns a flag so the report
can display the "Out of scope" message.
"""
from __future__ import annotations
import logging
from app.config import settings

logger = logging.getLogger("traffic_trends")

import requests

def fetch_traffic_data(domain: str) -> dict | None:
    api_key = getattr(settings, "SEO_API_KEY", "")
    
    if not api_key:
        return None
        
    try:
        url = "https://api.seranking.com/v1/domain/overview/db"
        headers = {
            "Authorization": f"Token {api_key}",
            "Content-Type": "application/json"
        }
        # Using 'us' as default database, can be configurable
        params = {"domain": domain, "source": "us"}
        
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            organic = data.get("organic", {})
            return {
                "estimated_traffic": int(organic.get("traffic_sum", 0)),
                "ranking_keywords": organic.get("keywords_count", 0),
                "data_source": "SE Ranking (US)"
            }
        else:
            logger.warning(f"SE Ranking Traffic API error: {resp.status_code}")
    except Exception as e:
        logger.error(f"Failed to fetch traffic data: {e}")
        
    return None
