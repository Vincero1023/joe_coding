from unittest.mock import patch

from app.analyzer.main import analyze_keywords, run
from app.analyzer.scorer import (
    calculate_attackability_score,
    calculate_final_score,
    calculate_opportunity,
    calculate_profit,
    calculate_profitability_score,
    classify_attackability_grade,
    classify_golden_bucket,
    classify_profitability_grade,
)


def test_profit_and_opportunity_helpers_return_scaled_values() -> None:
    profit = calculate_profit(500.0, 12.0)
    opportunity = calculate_opportunity(1000.0, 250.0)
    final_score = calculate_final_score(80.0, 60.0, 40.0)

    assert profit == 6.0
    assert opportunity == 4.0
    assert final_score == 63.0


def test_analyzer_heuristic_scores_are_not_collapsed_to_ones() -> None:
    with patch("app.analyzer.main.build_searchad_keyword_tool_index", return_value={}), patch(
        "app.analyzer.main.build_searchad_bid_index",
        return_value={},
    ), patch(
        "app.analyzer.main.build_blog_search_index",
        return_value={},
    ):
        result = analyze_keywords(
            [
                {"keyword": "loan compare", "root_origin": "loan"},
                {"keyword": "government registration notice", "root_origin": "government"},
            ]
        )

    assert len(result) == 2
    assert result[0]["keyword"] == "loan compare"
    assert result[0]["score"] > result[1]["score"]
    assert result[0]["metrics"]["volume"] > result[1]["metrics"]["volume"]
    assert result[0]["analysis_mode"] == "heuristic"
    assert result[0]["confidence"] < 0.5


def test_analyzer_uses_keyword_stats_text_when_available() -> None:
    result = run(
        {
            "keywords_text": "butter ricecake\nseoul butter ricecake",
            "keyword_stats_text": (
                "butter ricecake\t149800\t733000\t882800\t14202\t69.1\t522.7\t591.8\t500\t190\t130\n"
                "seoul butter ricecake\t3180\t24300\t27480\t99539\t2.9\t20\t22.9\t240\t70\t70"
            ),
        }
    )

    analyzed = result["analyzed_keywords"]
    assert len(analyzed) == 2
    assert analyzed[0]["keyword"] == "butter ricecake"
    assert analyzed[0]["analysis_mode"] == "search_metrics"
    assert analyzed[0]["metrics"]["volume"] == 882800.0
    assert analyzed[0]["metrics"]["cpc"] == 273.3333
    assert analyzed[0]["metrics"]["bid"] == 500.0
    assert analyzed[0]["confidence"] >= 0.8


def test_analyzer_uses_sample_style_score_tiers_for_measured_stats() -> None:
    result = run(
        {
            "keywords_text": "samchuly bike price",
            "keyword_stats_items": [
                {
                    "keyword": "samchuly bike price",
                    "pc_searches": 150,
                    "mobile_searches": 1490,
                    "blog_results": 30741,
                    "pc_clicks": 3.9,
                    "mobile_clicks": 82.5,
                    "bid_1": 440,
                    "bid_2": 420,
                    "bid_3": 210,
                }
            ],
        }
    )

    analyzed = result["analyzed_keywords"]
    assert len(analyzed) == 1
    assert analyzed[0]["score"] == 29.0
    assert analyzed[0]["grade"] == "D"
    assert analyzed[0]["metrics"]["cpc_score"] == 10.0
    assert analyzed[0]["metrics"]["search_volume_score"] == 60.0
    assert analyzed[0]["metrics"]["rarity_score"] == 15.0


def test_dual_axis_labels_are_attached_to_analyzed_keywords() -> None:
    result = run(
        {
            "keywords_text": "insurance compare",
            "keyword_stats_items": [
                {
                    "keyword": "insurance compare",
                    "pc_searches": 1300,
                    "mobile_searches": 9200,
                    "blog_results": 4800,
                    "pc_clicks": 48.0,
                    "mobile_clicks": 122.0,
                    "bid_1": 9200,
                    "bid_2": 7100,
                    "bid_3": 5200,
                }
            ],
        }
    )

    analyzed = result["analyzed_keywords"]
    assert len(analyzed) == 1
    assert analyzed[0]["profitability_grade"] in {"A", "B", "C", "D", "E", "F"}
    assert analyzed[0]["attackability_grade"] in {"1", "2", "3", "4", "5", "6"}
    assert analyzed[0]["combo_grade"] == (
        f"{analyzed[0]['profitability_grade']}{analyzed[0]['attackability_grade']}"
    )
    assert analyzed[0]["golden_bucket"] in {"gold", "promising", "experimental", "hold"}
    assert "click_potential_score" in analyzed[0]["metrics"]
    assert "click_yield_score" in analyzed[0]["metrics"]
    assert "exposure_signal_score" in analyzed[0]["metrics"]
    assert "opportunity_score" in analyzed[0]["metrics"]
    assert "competition_score" in analyzed[0]["metrics"]


def test_dual_axis_helpers_classify_gold_combo() -> None:
    profitability_score = calculate_profitability_score(90.0, 90.0, 240.0)
    attackability_score = calculate_attackability_score(4.5, 35.0, 0.35, 90.0)

    profitability_grade = classify_profitability_grade(profitability_score)
    attackability_grade = classify_attackability_grade(attackability_score)

    assert profitability_grade == "A"
    assert attackability_grade == "2"
    assert classify_golden_bucket(profitability_grade, attackability_grade) == "gold"


def test_profitability_score_keeps_search_volume_as_minor_signal() -> None:
    high_volume_score = calculate_profitability_score(80.0, 100.0, 60.0)
    low_volume_score = calculate_profitability_score(80.0, 10.0, 60.0)

    assert round(high_volume_score - low_volume_score, 1) == 9.0


def test_attackability_score_rewards_real_click_activity() -> None:
    base_score = calculate_attackability_score(
        2.0,
        35.0,
        0.4,
        60.0,
        total_clicks=0.0,
        search_volume=2400.0,
    )
    active_score = calculate_attackability_score(
        2.0,
        35.0,
        0.4,
        60.0,
        total_clicks=84.0,
        search_volume=2400.0,
    )

    assert active_score > base_score


def test_analyzer_matches_sample_detail_for_moderate_blog_counts() -> None:
    result = run(
        {
            "keywords_text": "kim gilli medal count",
            "keyword_stats_items": [
                {
                    "keyword": "kim gilli medal count",
                    "pc_searches": 40,
                    "mobile_searches": 480,
                    "blog_results": 4659,
                    "pc_clicks": 0,
                    "mobile_clicks": 0,
                    "bid_1": 70,
                    "bid_2": 70,
                    "bid_3": 70,
                }
            ],
        }
    )

    analyzed = result["analyzed_keywords"]
    assert len(analyzed) == 1
    assert analyzed[0]["score"] == 22.0
    assert analyzed[0]["grade"] == "F"
    assert analyzed[0]["metrics"]["cpc_score"] == 10.0
    assert analyzed[0]["metrics"]["search_volume_score"] == 25.0
    assert analyzed[0]["metrics"]["rarity_score"] == 35.0


def test_measured_low_score_keywords_are_kept_in_analysis_results() -> None:
    result = run(
        {
            "keywords_text": "face blackhead",
            "keyword_stats_items": [
                {
                    "keyword": "face blackhead",
                    "pc_searches": 20,
                    "mobile_searches": 140,
                    "blog_results": 390097,
                    "pc_clicks": 0,
                    "mobile_clicks": 2.5,
                    "bid_1": 1570,
                    "bid_2": 1560,
                    "bid_3": 1470,
                }
            ],
        }
    )

    analyzed = result["analyzed_keywords"]
    assert len(analyzed) == 1
    assert analyzed[0]["score"] == 17.0
    assert analyzed[0]["grade"] == "F"
    assert analyzed[0]["analysis_mode"] == "search_metrics"


def test_measured_metrics_do_not_backfill_missing_values_from_heuristics() -> None:
    result = run(
        {
            "keywords_text": "partial measured keyword",
            "searchad": {"enabled": False},
            "naver_search_api": {"enabled": False},
            "keyword_stats_items": [
                {
                    "keyword": "partial measured keyword",
                    "blog_results": 19,
                }
            ],
        }
    )

    analyzed = result["analyzed_keywords"]
    assert len(analyzed) == 1
    assert analyzed[0]["analysis_mode"] == "search_metrics"
    assert analyzed[0]["metrics"]["volume"] == 0.0
    assert analyzed[0]["metrics"]["cpc"] == 0.0
    assert analyzed[0]["metrics"]["bid"] == 0.0
    assert analyzed[0]["metrics"]["total_clicks"] == 0.0


def test_analyzer_filters_out_extremely_long_keywords() -> None:
    result = run(
        [
            {
                "keyword": "seoul gangnam restaurant recommendation comparison review price summary side effects types",
                "root_origin": "seoul gangnam restaurant",
            },
        ]
    )

    assert result == []
