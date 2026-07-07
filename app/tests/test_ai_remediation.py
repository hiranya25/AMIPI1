import pytest
from app.models import Issue
from app.ai_remediation import enrich_issues_with_remediation
from dataclasses import replace

def test_enrich_issues_reconstruction():
    # Simulate a raw finding dict that contains all the fields, including issue_type
    sample_finding = {
        "category": "SEO",
        "issue_type": "missing_robots_txt",
        "severity": "medium",
        "page_url": "https://example.com",
        "message": "robots.txt is missing",
        "details": None
    }
    
    # 1. Ensure we can build an Issue from this dict without raising an error
    # Because Issue requires explicit kwargs, this works properly.
    issue = Issue(**sample_finding)
    assert issue.issue_type == "missing_robots_txt"
    
    # 2. Enrich the issue with remediation (simulating the pipeline)
    enriched_list = enrich_issues_with_remediation([issue])
    enriched_issue = enriched_list[0]
    
    # 3. Confirm it didn't raise and the values are correct
    assert enriched_issue.issue_type == "missing_robots_txt"
    assert enriched_issue.how_to_fix == "Create a robots.txt file at the root of the domain."
    
    # 4. Confirm it doesn't mutate the original
    assert issue.how_to_fix is None
