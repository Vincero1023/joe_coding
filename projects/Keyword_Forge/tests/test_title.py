from unittest.mock import patch

from app.title.category_detector import detect_category
from app.title.main import run
from app.title.rules import NAVER_HOME_MAX_LENGTH


def test_detect_category_handles_finance_keyword() -> None:
    assert detect_category("보험 추천") == "finance"


def test_title_generator_returns_two_titles_per_type() -> None:
    result = run(
        [
            {
                "keyword": "보험 추천",
                "score": 1.0,
                "metrics": {
                    "volume": 1.0,
                    "cpc": 1.0,
                    "competition": 0.7,
                    "bid": 1.0,
                    "profit": 1.0,
                    "opportunity": 1.4286,
                },
            }
        ]
    )

    assert len(result) == 1
    assert len(result[0]["titles"]["naver_home"]) == 2
    assert len(result[0]["titles"]["blog"]) == 2
    assert all("보험 추천" in title for title in result[0]["titles"]["naver_home"])
    assert all(len(title) <= NAVER_HOME_MAX_LENGTH for title in result[0]["titles"]["naver_home"])


def test_title_generator_preserves_keyword_text() -> None:
    result = run(
        [
            {
                "keyword": "제주 여행 코스",
                "score": 0.82,
                "metrics": {
                    "volume": 0.7,
                    "cpc": 0.7,
                    "competition": 0.4,
                    "bid": 0.6,
                    "profit": 0.42,
                    "opportunity": 1.75,
                },
            }
        ]
    )

    assert result[0]["keyword"] == "제주 여행 코스"
    assert all("제주 여행 코스" in title for title in result[0]["titles"]["blog"])


def test_title_generator_supports_ai_mode() -> None:
    with patch(
        "app.title.title_generator.request_ai_titles",
        return_value=[
            {
                "keyword": "보험 추천",
                "titles": {
                    "naver_home": ["보험 추천 지금 비교 포인트 2가지", "보험 추천 선택 기준 달라졌다"],
                    "blog": ["보험 추천 완벽 가이드", "보험 추천 비교 포인트 정리"],
                },
            }
        ],
    ):
        result = run(
            {
                "selected_keywords": [
                    {
                        "keyword": "보험 추천",
                        "score": 1.0,
                    }
                ],
                "title_options": {
                    "mode": "ai",
                    "provider": "openai",
                    "api_key": "test-key",
                    "model": "gpt-4o-mini",
                },
            }
        )

    assert result["generation_meta"]["used_mode"] == "ai"
    assert result["generation_meta"]["provider"] == "openai"
    assert result["generated_titles"][0]["titles"]["blog"][0] == "보험 추천 완벽 가이드"


def test_title_generator_falls_back_to_template_when_api_key_missing() -> None:
    result = run(
        {
            "selected_keywords": [
                {
                    "keyword": "보험 추천",
                    "score": 1.0,
                }
            ],
            "title_options": {
                "mode": "ai",
                "provider": "openai",
                "api_key": "",
            },
        }
    )

    assert result["generation_meta"]["used_mode"] == "template_fallback"
    assert result["generation_meta"]["fallback_reason"] == "missing_api_key"
    assert len(result["generated_titles"][0]["titles"]["naver_home"]) == 2
