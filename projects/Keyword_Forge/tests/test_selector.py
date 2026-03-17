from app.selector.main import run
from app.selector.service import is_golden_keyword



def test_is_golden_keyword_accepts_profitable_keyword() -> None:
    item = {
        "keyword": "보험 추천",
        "metrics": {
            "volume": 1.0,
            "cpc": 1.0,
            "competition": 0.7,
            "bid": 1.0,
            "profit": 1.0,
            "opportunity": 1.4286,
        },
    }

    assert is_golden_keyword(item) is True



def test_is_golden_keyword_rejects_low_monetization_keyword() -> None:
    item = {
        "keyword": "뜻 정리",
        "metrics": {
            "volume": 1.0,
            "cpc": 0.3,
            "competition": 1.0,
            "bid": 0.3,
            "profit": 0.09,
            "opportunity": 1.0,
        },
    }

    assert is_golden_keyword(item) is False



def test_selector_returns_only_golden_keywords() -> None:
    result = run(
        [
            {
                "keyword": "보험 추천",
                "score": 1.0,
                "priority": "high",
                "metrics": {
                    "volume": 1.0,
                    "cpc": 1.0,
                    "competition": 0.7,
                    "bid": 1.0,
                    "profit": 1.0,
                    "opportunity": 1.4286,
                },
            },
            {
                "keyword": "뜻 정리",
                "score": 0.454,
                "priority": "low",
                "metrics": {
                    "volume": 1.0,
                    "cpc": 0.3,
                    "competition": 1.0,
                    "bid": 0.3,
                    "profit": 0.09,
                    "opportunity": 1.0,
                },
            },
        ]
    )

    assert len(result) == 1
    assert result[0]["keyword"] == "보험 추천"
