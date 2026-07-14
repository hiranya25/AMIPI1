from app.audits.backlinks import _parse_backlink_response


def test_parse_se_ranking_summary_response():
    data = {
        "summary": [
            {
                "target": "amipi.com",
                "backlinks": 1458,
                "refdomains": 90,
            }
        ]
    }

    assert _parse_backlink_response(data) == {
        "total_backlinks": 1458,
        "referring_domains": 90,
        "data_source": "SE Ranking",
    }


def test_parse_legacy_flat_response_shape():
    data = {
        "backlinks_count": "42",
        "referring_domains": "7",
    }

    assert _parse_backlink_response(data) == {
        "total_backlinks": 42,
        "referring_domains": 7,
        "data_source": "SE Ranking",
    }


def test_parse_unexpected_response_returns_none():
    assert _parse_backlink_response({"summary": []}) is None
