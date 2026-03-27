from pathlib import Path
from unittest.mock import patch

from app.selector.cannibalization import build_cannibalization_report
from app.selector.longtail import verify_longtail_candidates
from app.selector.main import run
from app.selector.serp_summary import parse_serp_titles, summarize_serp_competition
from app.selector.service import is_golden_keyword


def test_is_golden_keyword_accepts_balanced_metric_backed_keyword() -> None:
    item = {
        "keyword": "insurance compare",
        "score": 74.0,
        "analysis_mode": "search_metrics",
        "confidence": 0.92,
        "metrics": {
            "volume": 12500.0,
            "cpc": 420.0,
            "competition": 0.42,
            "bid": 310.0,
            "profit": 26.0,
            "opportunity": 2.4,
            "monetization_score": 60.0,
            "rarity_score": 38.0,
            "search_volume_score": 90.0,
            "total_clicks": 84.0,
        },
    }

    assert is_golden_keyword(item) is True


def test_is_golden_keyword_rejects_low_value_heuristic_keyword() -> None:
    item = {
        "keyword": "government registration notice",
        "score": 36.0,
        "analysis_mode": "heuristic",
        "confidence": 0.35,
        "metrics": {
            "volume": 420.0,
            "cpc": 60.0,
            "competition": 0.58,
            "bid": 44.0,
            "profit": 0.4,
            "opportunity": 1.7,
            "monetization_score": 22.0,
            "rarity_score": 18.0,
            "search_volume_score": 25.0,
            "total_clicks": 2.0,
        },
    }

    assert is_golden_keyword(item) is False


def test_is_golden_keyword_rejects_template_heavy_keyword_even_with_good_metrics() -> None:
    item = {
        "keyword": "로지텍 마우스 추천 기준",
        "score": 74.0,
        "analysis_mode": "search_metrics",
        "confidence": 0.93,
        "metrics": {
            "volume": 8200.0,
            "cpc": 320.0,
            "competition": 0.38,
            "bid": 240.0,
            "profit": 18.0,
            "opportunity": 2.3,
            "monetization_score": 58.0,
            "rarity_score": 36.0,
            "search_volume_score": 84.0,
            "total_clicks": 72.0,
        },
    }

    assert is_golden_keyword(item) is False


def test_selector_returns_only_golden_keywords() -> None:
    result = run(
        [
            {
                "keyword": "insurance compare",
                "score": 74.0,
                "analysis_mode": "search_metrics",
                "confidence": 0.92,
                "priority": "high",
                "metrics": {
                    "volume": 12500.0,
                    "cpc": 420.0,
                    "competition": 0.42,
                    "bid": 310.0,
                    "profit": 26.0,
                    "opportunity": 2.4,
                    "monetization_score": 60.0,
                    "rarity_score": 38.0,
                    "search_volume_score": 90.0,
                    "total_clicks": 84.0,
                },
            },
            {
                "keyword": "government registration notice",
                "score": 36.0,
                "analysis_mode": "heuristic",
                "confidence": 0.35,
                "priority": "low",
                "metrics": {
                    "volume": 420.0,
                    "cpc": 60.0,
                    "competition": 0.58,
                    "bid": 44.0,
                    "profit": 0.4,
                    "opportunity": 1.7,
                    "monetization_score": 22.0,
                    "rarity_score": 18.0,
                    "search_volume_score": 25.0,
                    "total_clicks": 2.0,
                },
            },
        ]
    )

    assert len(result) == 1
    assert result[0]["keyword"] == "insurance compare"
    assert result[0]["selection_mode"] == "golden_combo"


def test_selector_grade_filter_returns_allowed_grades_without_golden_filtering() -> None:
    result = run(
        {
            "analyzed_keywords": [
                {
                    "keyword": "정보형 키워드 A",
                    "grade": "A",
                    "score": 72.0,
                    "analysis_mode": "search_metrics",
                    "confidence": 0.91,
                    "metrics": {
                        "volume": 820.0,
                        "cpc": 55.0,
                        "competition": 1.3,
                        "opportunity": 1.3,
                        "monetization_score": 22.0,
                        "rarity_score": 26.0,
                    },
                },
                {
                    "keyword": "정보형 키워드 D",
                    "grade": "D",
                    "score": 31.0,
                    "analysis_mode": "search_metrics",
                    "confidence": 0.88,
                    "metrics": {
                        "volume": 410.0,
                        "cpc": 15.0,
                        "competition": 1.7,
                        "opportunity": 1.1,
                        "monetization_score": 10.0,
                        "rarity_score": 14.0,
                    },
                },
            ],
            "select_options": {
                "mode": "grade_filter",
                "allowed_grades": ["D"],
            },
        }
    )

    assert len(result["selected_keywords"]) == 1
    assert result["selected_keywords"][0]["keyword"] == "정보형 키워드 D"
    assert result["selected_keywords"][0]["selection_mode"] == "grade_filter"


def test_selector_response_includes_debug_payload() -> None:
    result = run(
        {
            "analyzed_keywords": [
                {
                    "keyword": "insurance compare",
                    "score": 74.0,
                    "analysis_mode": "search_metrics",
                    "confidence": 0.92,
                    "metrics": {
                        "volume": 12500.0,
                        "cpc": 420.0,
                        "competition": 0.42,
                        "bid": 310.0,
                        "profit": 26.0,
                        "opportunity": 2.4,
                        "monetization_score": 60.0,
                        "rarity_score": 38.0,
                        "search_volume_score": 90.0,
                        "total_clicks": 84.0,
                    },
                },
            ],
            "selection_export": {
                "enabled": False,
            },
        }
    )

    assert result["debug"]["stage"] == "selector"
    assert result["debug"]["summary"]["total_calls"] == 0
    assert result["debug"]["selection_summary"]["input_keyword_count"] == 1
    assert result["debug"]["selection_summary"]["selected_keyword_count"] == 1


def test_selector_combo_filter_returns_matching_two_axis_keywords() -> None:
    result = run(
        {
            "analyzed_keywords": [
                {
                    "keyword": "true_gold",
                    "profitability_grade": "A",
                    "attackability_grade": "2",
                    "combo_grade": "A2",
                    "golden_bucket": "gold",
                    "score": 73.0,
                    "metrics": {"volume": 2400.0, "cpc": 450.0},
                },
                {
                    "keyword": "hold_keyword",
                    "profitability_grade": "D",
                    "attackability_grade": "4",
                    "combo_grade": "D4",
                    "golden_bucket": "hold",
                    "score": 28.0,
                    "metrics": {"volume": 60.0, "cpc": 20.0},
                },
            ],
            "select_options": {
                "mode": "combo_filter",
                "allowed_profitability_grades": ["A", "B", "C"],
                "allowed_attackability_grades": ["1", "2", "3"],
            },
        }
    )

    assert len(result["selected_keywords"]) == 1
    assert result["selected_keywords"][0]["keyword"] == "true_gold"
    assert result["selected_keywords"][0]["selection_mode"] == "combo_filter"


def test_selector_grade_filter_uses_score_when_grade_is_missing() -> None:
    result = run(
        {
            "analyzed_keywords": [
                {
                    "keyword": "score_only_d_grade",
                    "score": 31.0,
                    "analysis_mode": "search_metrics",
                    "confidence": 0.9,
                    "metrics": {
                        "volume": 210.0,
                        "cpc": 44.0,
                        "competition": 1.2,
                        "opportunity": 1.2,
                        "monetization_score": 18.0,
                        "rarity_score": 16.0,
                    },
                },
            ],
            "select_options": {
                "mode": "grade_filter",
                "allowed_grades": ["D"],
            },
        }
    )

    assert len(result["selected_keywords"]) == 1
    assert result["selected_keywords"][0]["keyword"] == "score_only_d_grade"
    assert result["selected_keywords"][0]["selection_mode"] == "grade_filter"


def test_selector_builds_keyword_clusters_for_selected_keywords() -> None:
    result = run(
        {
            "analyzed_keywords": [
                {
                    "keyword": "보험 추천",
                    "grade": "A",
                    "profitability_grade": "A",
                    "attackability_grade": "2",
                    "combo_grade": "A2",
                    "golden_bucket": "gold",
                    "score": 76.0,
                    "metrics": {"volume": 1200.0, "cpc": 210.0},
                },
                {
                    "keyword": "보험 비교",
                    "grade": "A",
                    "profitability_grade": "A",
                    "attackability_grade": "2",
                    "combo_grade": "A2",
                    "golden_bucket": "gold",
                    "score": 73.0,
                    "metrics": {"volume": 980.0, "cpc": 180.0},
                },
                {
                    "keyword": "보험 가입 조건",
                    "grade": "A",
                    "profitability_grade": "B",
                    "attackability_grade": "1",
                    "combo_grade": "B1",
                    "golden_bucket": "gold",
                    "score": 71.0,
                    "metrics": {"volume": 740.0, "cpc": 165.0},
                },
                {
                    "keyword": "제주 여행 코스",
                    "grade": "A",
                    "profitability_grade": "C",
                    "attackability_grade": "2",
                    "combo_grade": "C2",
                    "golden_bucket": "promising",
                    "score": 69.0,
                    "metrics": {"volume": 1320.0, "cpc": 90.0},
                },
            ],
            "select_options": {
                "mode": "combo_filter",
                "allowed_profitability_grades": ["A", "B", "C"],
                "allowed_attackability_grades": ["1", "2", "3"],
            },
        }
    )

    assert len(result["selected_keywords"]) == 4
    assert result["content_map_summary"]["cluster_count"] == 2
    assert result["content_map_summary"]["keyword_count"] == 4
    assert result["cannibalization_report"]["summary"]["candidate_count"] >= 4

    insurance_cluster = next(
        cluster
        for cluster in result["keyword_clusters"]
        if "보험 추천" in cluster["all_keywords"]
    )
    assert insurance_cluster["keyword_count"] == 3
    assert insurance_cluster["cluster_type"] == "multi_article"
    assert insurance_cluster["recommended_article_count"] == 2
    assert insurance_cluster["top_combo"] == "A2"


def test_selector_content_map_splits_articles_by_intent() -> None:
    result = run(
        {
            "analyzed_keywords": [
                {
                    "keyword": "보험 추천",
                    "grade": "A",
                    "profitability_grade": "A",
                    "attackability_grade": "2",
                    "combo_grade": "A2",
                    "golden_bucket": "gold",
                    "score": 77.0,
                    "metrics": {"volume": 1100.0, "cpc": 220.0},
                },
                {
                    "keyword": "보험 뜻 정리",
                    "grade": "A",
                    "profitability_grade": "C",
                    "attackability_grade": "1",
                    "combo_grade": "C1",
                    "golden_bucket": "promising",
                    "score": 70.0,
                    "metrics": {"volume": 860.0, "cpc": 80.0},
                },
                {
                    "keyword": "보험 가입 조건",
                    "grade": "A",
                    "profitability_grade": "B",
                    "attackability_grade": "1",
                    "combo_grade": "B1",
                    "golden_bucket": "gold",
                    "score": 72.0,
                    "metrics": {"volume": 690.0, "cpc": 150.0},
                },
            ],
            "select_options": {
                "mode": "combo_filter",
                "allowed_profitability_grades": ["A", "B", "C"],
                "allowed_attackability_grades": ["1", "2", "3"],
            },
        }
    )

    cluster = result["keyword_clusters"][0]
    intent_keys = {slot["intent_key"] for slot in cluster["article_plan"]}

    assert cluster["keyword_count"] == 3
    assert cluster["recommended_article_count"] == 3
    assert intent_keys == {"commercial", "info", "action"}


def test_selector_builds_longtail_suggestions_from_clustered_keywords() -> None:
    result = run(
        {
            "analyzed_keywords": [
                {
                    "keyword": "보험 추천",
                    "profitability_grade": "A",
                    "attackability_grade": "2",
                    "combo_grade": "A2",
                    "golden_bucket": "gold",
                    "score": 76.0,
                    "metrics": {"volume": 1200.0, "cpc": 210.0},
                },
                {
                    "keyword": "보험 비교",
                    "profitability_grade": "A",
                    "attackability_grade": "2",
                    "combo_grade": "A2",
                    "golden_bucket": "gold",
                    "score": 73.0,
                    "metrics": {"volume": 980.0, "cpc": 180.0},
                },
                {
                    "keyword": "보험 가입 조건",
                    "profitability_grade": "B",
                    "attackability_grade": "1",
                    "combo_grade": "B1",
                    "golden_bucket": "gold",
                    "score": 71.0,
                    "metrics": {"volume": 740.0, "cpc": 165.0},
                },
            ],
            "select_options": {
                "mode": "combo_filter",
                "allowed_profitability_grades": ["A", "B", "C"],
                "allowed_attackability_grades": ["1", "2", "3"],
            },
        }
    )

    suggestions = result["longtail_suggestions"]
    assert suggestions
    assert result["longtail_summary"]["suggestion_count"] == len(suggestions)
    assert any(item["projected_combo_grade"] for item in suggestions)
    assert any("보험" in item["longtail_keyword"] for item in suggestions)


def test_selector_uses_editorial_fallback_and_still_builds_general_longtails() -> None:
    result = run(
        {
            "analyzed_keywords": [
                {
                    "keyword": "컴퓨터 모니터",
                    "profitability_grade": "D",
                    "attackability_grade": "4",
                    "combo_grade": "D4",
                    "golden_bucket": "hold",
                    "score": 39.0,
                    "analysis_mode": "search_metrics",
                    "confidence": 0.98,
                    "metrics": {"volume": 16260.0, "cpc": 2653.0},
                },
                {
                    "keyword": "포터블 모니터",
                    "profitability_grade": "D",
                    "attackability_grade": "3",
                    "combo_grade": "D3",
                    "golden_bucket": "hold",
                    "score": 39.0,
                    "analysis_mode": "search_metrics",
                    "confidence": 0.98,
                    "metrics": {"volume": 24610.0, "cpc": 1163.0},
                },
                {
                    "keyword": "벤큐 2546k",
                    "profitability_grade": "D",
                    "attackability_grade": "1",
                    "combo_grade": "D1",
                    "golden_bucket": "experimental",
                    "score": 34.0,
                    "analysis_mode": "search_metrics",
                    "confidence": 0.98,
                    "metrics": {"volume": 2730.0, "cpc": 70.0},
                },
                {
                    "keyword": "벤큐 ma270s",
                    "profitability_grade": "D",
                    "attackability_grade": "1",
                    "combo_grade": "D1",
                    "golden_bucket": "experimental",
                    "score": 34.0,
                    "analysis_mode": "search_metrics",
                    "confidence": 0.98,
                    "metrics": {"volume": 1500.0, "cpc": 70.0},
                },
            ],
        }
    )

    selected_keywords = result["selected_keywords"]
    assert len(selected_keywords) == 4
    assert all(item["selection_mode"] == "editorial_support" for item in selected_keywords)
    assert any(item["keyword"] == "벤큐 2546k" for item in selected_keywords)
    assert any(item["keyword"] == "포터블 모니터" for item in selected_keywords)

    longtail_keywords = [item["longtail_keyword"] for item in result["longtail_suggestions"]]
    assert longtail_keywords
    assert any(
        "컴퓨터 모니터" in keyword
        and any(term in keyword for term in ("실사용 차이", "장단점", "자주 생기는 문제", "설정 팁"))
        for keyword in longtail_keywords
    )
    assert any("벤큐 2546k" in keyword for keyword in longtail_keywords)


def test_selector_tops_up_small_default_selection_with_editorial_support_candidates() -> None:
    result = run(
        {
            "analyzed_keywords": [
                {
                    "keyword": "로지텍 mx master 3s",
                    "profitability_grade": "A",
                    "attackability_grade": "2",
                    "combo_grade": "A2",
                    "golden_bucket": "gold",
                    "score": 77.0,
                    "analysis_mode": "search_metrics",
                    "confidence": 0.96,
                    "metrics": {"volume": 5400.0, "cpc": 420.0},
                },
                {
                    "keyword": "로지텍 버티컬 마우스",
                    "profitability_grade": "D",
                    "attackability_grade": "1",
                    "combo_grade": "D1",
                    "golden_bucket": "experimental",
                    "score": 36.0,
                    "analysis_mode": "search_metrics",
                    "confidence": 0.95,
                    "metrics": {"volume": 2200.0, "cpc": 110.0},
                },
                {
                    "keyword": "로지텍 마우스 설정",
                    "profitability_grade": "D",
                    "attackability_grade": "2",
                    "combo_grade": "D2",
                    "golden_bucket": "experimental",
                    "score": 34.0,
                    "analysis_mode": "search_metrics",
                    "confidence": 0.94,
                    "metrics": {"volume": 1800.0, "cpc": 80.0},
                },
                {
                    "keyword": "로지텍 g304",
                    "profitability_grade": "D",
                    "attackability_grade": "3",
                    "combo_grade": "D3",
                    "golden_bucket": "hold",
                    "score": 33.0,
                    "analysis_mode": "search_metrics",
                    "confidence": 0.91,
                    "metrics": {"volume": 4100.0, "cpc": 90.0},
                },
            ],
        }
    )

    selected_keywords = result["selected_keywords"]
    assert len(selected_keywords) == 4
    assert selected_keywords[0]["keyword"] == "로지텍 mx master 3s"
    assert selected_keywords[0]["selection_mode"] == "golden_combo"
    assert sum(1 for item in selected_keywords if item["selection_mode"] == "editorial_support") == 3


def test_selector_injects_seed_anchor_for_specific_intent_seed_when_selection_drifts() -> None:
    result = run(
        {
            "seed_input": "닌텐도 스위치2 사전예약",
            "analyzed_keywords": [
                {
                    "keyword": "닌텐도 스위치2 마리오카트",
                    "profitability_grade": "D",
                    "attackability_grade": "3",
                    "combo_grade": "D3",
                    "golden_bucket": "hold",
                    "score": 39.0,
                    "analysis_mode": "search_metrics",
                    "confidence": 0.98,
                    "metrics": {"volume": 17940.0, "cpc": 556.0},
                },
                {
                    "keyword": "닌텐도 스위치2 동물의숲",
                    "profitability_grade": "D",
                    "attackability_grade": "4",
                    "combo_grade": "D4",
                    "golden_bucket": "hold",
                    "score": 29.0,
                    "analysis_mode": "search_metrics",
                    "confidence": 0.98,
                    "metrics": {"volume": 6120.0, "cpc": 180.0},
                },
            ],
        }
    )

    assert result["selected_keywords"][0]["keyword"] == "닌텐도 스위치2 사전예약"
    assert result["selected_keywords"][0]["selection_mode"] == "seed_anchor"
    assert result["selected_keywords"][0]["selection_reason"] == "seed_intent_preserved"


def test_selector_does_not_inject_seed_anchor_for_broad_two_token_seed() -> None:
    result = run(
        {
            "seed_input": "로지텍 키보드",
            "analyzed_keywords": [
                {
                    "keyword": "독거미 키보드",
                    "profitability_grade": "C",
                    "attackability_grade": "1",
                    "combo_grade": "C1",
                    "golden_bucket": "promising",
                    "score": 43.0,
                    "analysis_mode": "search_metrics",
                    "confidence": 0.98,
                    "metrics": {"volume": 87400.0, "cpc": 483.0},
                },
                {
                    "keyword": "큐센 q104",
                    "profitability_grade": "D",
                    "attackability_grade": "1",
                    "combo_grade": "D1",
                    "golden_bucket": "experimental",
                    "score": 34.0,
                    "analysis_mode": "search_metrics",
                    "confidence": 0.98,
                    "metrics": {"volume": 3630.0, "cpc": 756.0},
                },
            ],
        }
    )

    assert all(item["keyword"] != "로지텍 키보드" for item in result["selected_keywords"])


def test_selector_keeps_guide_and_checklist_suffixes_optional() -> None:
    analyzed_keywords = [
        {
            "keyword": "보험 추천",
            "profitability_grade": "A",
            "attackability_grade": "2",
            "combo_grade": "A2",
            "golden_bucket": "gold",
            "score": 76.0,
            "metrics": {"volume": 1200.0, "cpc": 210.0},
        },
        {
            "keyword": "보험 비교",
            "profitability_grade": "A",
            "attackability_grade": "2",
            "combo_grade": "A2",
            "golden_bucket": "gold",
            "score": 73.0,
            "metrics": {"volume": 980.0, "cpc": 180.0},
        },
        {
            "keyword": "보험 가입 조건",
            "profitability_grade": "B",
            "attackability_grade": "1",
            "combo_grade": "B1",
            "golden_bucket": "gold",
            "score": 71.0,
            "metrics": {"volume": 740.0, "cpc": 165.0},
        },
    ]

    default_result = run({"analyzed_keywords": analyzed_keywords})
    default_keywords = [item["longtail_keyword"] for item in default_result["longtail_suggestions"]]

    option_result = run(
        {
            "analyzed_keywords": analyzed_keywords,
            "select_options": {
                "longtail_options": {
                    "optional_suffix_keys": ["guide", "checklist"],
                }
            },
        }
    )
    option_keywords = [item["longtail_keyword"] for item in option_result["longtail_suggestions"]]

    assert not any(keyword.endswith("가이드") or keyword.endswith("체크리스트") for keyword in default_keywords)
    assert any(keyword.endswith("가이드") or keyword.endswith("체크리스트") for keyword in option_keywords)


def test_verify_longtail_candidates_merges_verified_analysis() -> None:
    selected_keywords = [
        {
            "keyword": "보험 추천",
            "profitability_grade": "A",
            "attackability_grade": "2",
            "combo_grade": "A2",
            "golden_bucket": "gold",
            "score": 76.0,
            "metrics": {"volume": 1200.0, "cpc": 210.0},
        },
        {
            "keyword": "보험 가입 조건",
            "profitability_grade": "B",
            "attackability_grade": "1",
            "combo_grade": "B1",
            "golden_bucket": "gold",
            "score": 71.0,
            "metrics": {"volume": 740.0, "cpc": 165.0},
        },
    ]
    select_result = run(
        {
            "selected_keywords": selected_keywords,
            "select_options": {
                "mode": "combo_filter",
                "allowed_profitability_grades": ["A", "B", "C"],
                "allowed_attackability_grades": ["1", "2", "3"],
            },
        }
    )
    suggestions = select_result["longtail_suggestions"]
    target_keyword = suggestions[0]["longtail_keyword"]

    with patch(
        "app.selector.longtail.analyzer_module.run",
        return_value={
            "analyzed_keywords": [
                {
                    "keyword": target_keyword,
                    "profitability_grade": "B",
                    "attackability_grade": "1",
                    "combo_grade": "B1",
                    "golden_bucket": "gold",
                    "analysis_mode": "search_metrics",
                    "score": 68.0,
                    "metrics": {
                        "volume": 380.0,
                        "cpc": 190.0,
                        "opportunity": 2.1,
                    },
                }
            ]
        },
    ):
        result = verify_longtail_candidates(
            {
                "selected_keywords": selected_keywords,
                "keyword_clusters": select_result["keyword_clusters"],
                "longtail_suggestions": suggestions[:1],
            }
        )

    assert len(result["verified_longtail_suggestions"]) == 1
    verified = result["verified_longtail_suggestions"][0]
    assert verified["verification_status"] == "pass"
    assert verified["verified_combo_grade"] == "B1"
    assert verified["verified_metrics"]["volume"] == 380.0
    assert result["longtail_verification_summary"]["pass_count"] == 1
    assert result["cannibalization_report"]["summary"]["candidate_count"] >= 3


def test_cannibalization_report_flags_same_intent_cluster_candidates() -> None:
    insurance_recommend = "\ubcf4\ud5d8 \ucd94\ucc9c"
    insurance_compare = "\ubcf4\ud5d8 \ube44\uad50"
    insurance_compare_guide = "\ubcf4\ud5d8 \ube44\uad50 \uac00\uc774\ub4dc"

    report = build_cannibalization_report(
        selected_items=[
            {"keyword": insurance_recommend, "score": 76.0},
            {"keyword": insurance_compare, "score": 73.0},
        ],
        keyword_clusters=[
            {
                "cluster_id": "cluster-01",
                "representative_keyword": insurance_recommend,
                "topic_terms": ["\ubcf4\ud5d8"],
                "recommended_article_count": 2,
                "all_keywords": [insurance_recommend, insurance_compare],
            }
        ],
        longtail_suggestions=[
            {
                "cluster_id": "cluster-01",
                "representative_keyword": insurance_recommend,
                "intent_key": "commercial",
                "longtail_keyword": insurance_compare_guide,
                "projected_score": 68.0,
                "verification_status": "pending",
            }
        ],
    )

    assert report["summary"]["issue_group_count"] == 1
    assert report["summary"]["high_risk_count"] == 1
    assert report["summary"]["safe_split_cluster_count"] == 1
    assert report["groups"][0]["recommended_action"] == "merge"
    assert report["groups"][0]["candidate_count"] == 3
    assert report["groups"][0]["primary_keyword"] == insurance_recommend
    assert any(item["source_type"] == "longtail" for item in report["groups"][0]["items"])


def test_serp_summary_parses_titles_and_builds_competition_summary() -> None:
    html = """
    <html>
      <body>
        <div class="title_area"><a href="https://blog.naver.com/post1" class="title_link">보험 추천 비교 포인트</a></div>
        <div class="title_area"><a href="https://blog.naver.com/post2" class="title_link">보험 추천 가격 비교 가이드</a></div>
        <div class="title_area"><a href="https://terms.naver.com/entry" class="title_link">보험 비교 기준 정리</a></div>
      </body>
    </html>
    """

    parsed_titles = parse_serp_titles(html)
    assert len(parsed_titles) == 3
    assert parsed_titles[0]["domain"] == "blog.naver.com"
    assert parsed_titles[2]["source_bucket"] == "official"

    summary = summarize_serp_competition(
        {
            "selected_keywords": [{"keyword": "\ubcf4\ud5d8 \ucd94\ucc9c", "score": 76.0}],
            "limit": 1,
        },
        fetch_html=lambda keyword: html,
    )["serp_competition_summary"]

    assert summary["summary"]["query_count"] == 1
    assert summary["summary"]["success_count"] == 1
    assert summary["queries"][0]["query"] == "\ubcf4\ud5d8 \ucd94\ucc9c"
    assert summary["queries"][0]["competition_level"] in {"medium", "high"}
    assert len(summary["queries"][0]["top_titles"]) == 3


def test_selector_scales_default_selection_for_large_measured_pool() -> None:
    analyzed_keywords = [
        {
            "keyword": f"large pool keyword {index}",
            "profitability_grade": "D",
            "attackability_grade": "1" if index % 3 == 0 else "2",
            "combo_grade": "D1" if index % 3 == 0 else "D2",
            "golden_bucket": "experimental",
            "score": 37.0 - (index * 0.05),
            "analysis_mode": "search_metrics",
            "confidence": 0.96,
            "metrics": {"volume": 2400.0 - index, "cpc": 90.0},
        }
        for index in range(50)
    ]

    result = run({"analyzed_keywords": analyzed_keywords})

    selected_keywords = result["selected_keywords"]
    assert len(selected_keywords) == 9
    assert all(item["selection_mode"] == "editorial_support" for item in selected_keywords)


def test_selector_can_export_selected_keywords_txt(tmp_path) -> None:
    result = run(
        {
            "mode": "category",
            "category": "비즈니스경제",
            "selection_export": {
                "enabled": True,
                "output_dir": str(tmp_path),
            },
            "analyzed_keywords": [
                {
                    "keyword": "보험 추천",
                    "profitability_grade": "A",
                    "attackability_grade": "2",
                    "combo_grade": "A2",
                    "golden_bucket": "gold",
                    "score": 76.0,
                    "analysis_mode": "search_metrics",
                    "metrics": {"volume": 1200.0, "cpc": 210.0},
                },
                {
                    "keyword": "ISA 계좌 개설",
                    "profitability_grade": "B",
                    "attackability_grade": "1",
                    "combo_grade": "B1",
                    "golden_bucket": "gold",
                    "score": 71.0,
                    "analysis_mode": "search_metrics",
                    "metrics": {"volume": 740.0, "cpc": 165.0},
                },
            ],
        }
    )

    export_payload = result["selection_export"]
    assert export_payload["row_count"] == len(result["selected_keywords"])
    live_path = next(Path(item["path"]) for item in export_payload["artifacts"] if item["format"] == "txt_live")
    archive_path = next(Path(item["path"]) for item in export_payload["artifacts"] if item["format"] == "txt_archive")
    assert live_path.exists()
    assert archive_path.exists()
    assert live_path.read_text(encoding="utf-8").splitlines() == [item["keyword"] for item in result["selected_keywords"]]
    assert live_path.name.endswith("__비즈니스경제.txt")
