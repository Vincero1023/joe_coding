from app.selector.main import run
from app.selector.service import is_golden_keyword


def test_is_golden_keyword_accepts_high_scoring_metric_backed_keyword() -> None:
    item = {
        "keyword": "운전자보험 비교",
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
        },
    }

    assert is_golden_keyword(item) is True


def test_is_golden_keyword_rejects_low_value_heuristic_keyword() -> None:
    item = {
        "keyword": "보험연수원 보수교육 수강신청",
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
        },
    }

    assert is_golden_keyword(item) is False


def test_selector_returns_only_golden_keywords() -> None:
    result = run(
        [
            {
                "keyword": "운전자보험 비교",
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
                },
            },
            {
                "keyword": "보험연수원 보수교육 수강신청",
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
                },
            },
        ]
    )

    assert len(result) == 1
    assert result[0]["keyword"] == "운전자보험 비교"
