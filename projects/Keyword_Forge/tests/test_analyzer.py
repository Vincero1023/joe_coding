from app.analyzer.main import analyze_keywords, run
from app.analyzer.metrics import (
    get_bid_score,
    get_competition_score,
    get_cpc_score,
    get_volume_score,
)
from app.analyzer.scorer import (
    calculate_final_score,
    calculate_opportunity,
    calculate_profit,
)


def test_metrics_follow_profit_driven_rules() -> None:
    assert get_cpc_score("보험 추천") == 1.0
    assert get_bid_score("보험 추천") == 1.0
    assert get_volume_score("보험 추천") == 1.0
    assert get_competition_score("보험 추천") == 1.0


def test_dual_layer_score_uses_profit_and_opportunity() -> None:
    profit = calculate_profit(1.0, 1.0)
    opportunity = calculate_opportunity(1.0, 1.0)
    final_score = calculate_final_score(profit, opportunity)

    assert profit == 1.0
    assert opportunity == 1.0
    assert final_score == 1.0


def test_analyzer_prioritizes_transactional_keywords() -> None:
    result = analyze_keywords(
        [
            {"keyword": "보험 추천", "root_origin": "보험"},
            {"keyword": "뜻 정리", "root_origin": "뜻"},
        ]
    )

    assert result[0]["keyword"] == "보험 추천"
    assert result[0]["priority"] == "high"
    assert result[0]["metrics"]["profit"] > result[-1]["metrics"]["profit"]
    assert result[0]["score"] > result[-1]["score"]


def test_analyzer_filters_out_extremely_long_keywords() -> None:
    result = run(
        [
            {"keyword": "서울 강남 맛집 추천 비교 후기 가격 정리", "root_origin": "서울 강남 맛집"},
        ]
    )

    assert result == []
