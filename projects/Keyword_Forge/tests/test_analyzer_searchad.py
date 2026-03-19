from unittest.mock import patch

from app.analyzer.keyword_stats import KeywordStats
from app.analyzer.main import run
from app.expander.utils.tokenizer import normalize_key


def test_analyzer_fills_missing_bids_from_searchad() -> None:
    keyword = "driver insurance compare"

    with patch("app.analyzer.main.build_searchad_keyword_tool_index", return_value={}), patch(
        "app.analyzer.main.build_blog_search_index",
        return_value={},
    ), patch(
        "app.analyzer.main.build_searchad_bid_index",
        return_value={
            normalize_key(keyword): KeywordStats(
                keyword=keyword,
                bid_1=1570.0,
                bid_2=1560.0,
                bid_3=1470.0,
                source="naver_searchad",
            )
        },
    ):
        result = run({"keywords_text": keyword})

    analyzed = result["analyzed_keywords"]
    assert len(analyzed) == 1
    assert analyzed[0]["analysis_mode"] == "search_metrics"
    assert analyzed[0]["metrics"]["cpc"] == 1533.3333
    assert analyzed[0]["metrics"]["bid"] == 1570.0
    assert analyzed[0]["metrics"]["bid_2"] == 1560.0
    assert analyzed[0]["confidence"] >= 0.65


def test_analyzer_keeps_existing_stats_over_searchad_bids() -> None:
    keyword = "driver insurance compare"

    with patch("app.analyzer.main.build_searchad_keyword_tool_index", return_value={}), patch(
        "app.analyzer.main.build_blog_search_index",
        return_value={},
    ), patch(
        "app.analyzer.main.build_searchad_bid_index",
        return_value={
            normalize_key(keyword): KeywordStats(
                keyword=keyword,
                bid_1=999.0,
                bid_2=888.0,
                bid_3=777.0,
                source="naver_searchad",
            )
        },
    ):
        result = run(
            {
                "keywords_text": keyword,
                "keyword_stats_items": [
                    {
                        "keyword": keyword,
                        "bid_1": 500.0,
                        "bid_2": 190.0,
                        "bid_3": 130.0,
                        "stats_source": "manual",
                    }
                ],
            }
        )

    analyzed = result["analyzed_keywords"]
    assert len(analyzed) == 1
    assert analyzed[0]["metrics"]["cpc"] == 273.3333
    assert analyzed[0]["metrics"]["bid"] == 500.0
    assert analyzed[0]["metrics"]["bid_2"] == 190.0
