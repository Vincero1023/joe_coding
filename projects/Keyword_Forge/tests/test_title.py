from unittest.mock import patch

from app.title.ai_client import TitleGenerationOptions
from app.title.category_detector import detect_category
from app.title.main import run
from app.title.rules import NAVER_HOME_MAX_LENGTH
from app.title.templates import build_blog_titles, build_naver_home_titles


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
    assert result[0]["quality_report"]["bundle_score"] > 0
    assert result[0]["quality_report"]["label"] in {"양호", "재검토", "재생성 권장"}


def test_template_titles_avoid_legacy_repetitive_phrases() -> None:
    naver_titles = build_naver_home_titles("평택 왁싱 남성전용", "general")
    blog_titles = build_blog_titles("평택 왁싱 남성전용", "general")
    all_titles = naver_titles + blog_titles

    banned_phrases = (
        "완벽 정리",
        "한 번에 정리",
        "갑자기 바뀌었다",
        "이유가 이상하다",
        "놓치면 손해",
        "비교 및 선택 기준 정리",
    )

    assert len(naver_titles) == 2
    assert len(blog_titles) == 2
    assert all("평택 왁싱 남성전용" in title for title in all_titles)
    assert not any(phrase in title for title in all_titles for phrase in banned_phrases)


def test_template_titles_follow_keyword_intent_patterns() -> None:
    review_titles = build_blog_titles("평택 밸리왁싱 후기", "general")
    action_titles = build_blog_titles("평택 밸리왁싱 예약", "general")
    profile_titles = build_blog_titles("함돈균 교수프로필", "general")

    assert any(("후기" in title or "평판" in title) for title in review_titles)
    assert not any("후기 후기" in title for title in review_titles)
    assert any(("준비" in title or "체크리스트" in title or "절차" in title) for title in action_titles)
    assert any(("이력" in title or "정보" in title) for title in profile_titles)


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
    assert result["generation_meta"]["quality_summary"]["total_count"] == 1


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
    assert result["generated_titles"][0]["quality_report"]["summary"]


def test_title_generation_options_keep_custom_system_prompt() -> None:
    options = TitleGenerationOptions.from_input(
        {
            "title_options": {
                "mode": "ai",
                "provider": "openai",
                "system_prompt": "제목 첫 단어는 항상 키워드여야 한다.",
            }
        }
    )

    assert options.system_prompt == "제목 첫 단어는 항상 키워드여야 한다."
    assert "Additional guidance" in options.effective_system_prompt
    assert "avoid repeating the same headline skeleton" in options.effective_system_prompt.lower()


def test_title_generator_auto_retries_low_quality_ai_titles() -> None:
    with patch(
        "app.title.title_generator.request_ai_titles",
        side_effect=[
            [
                {
                    "keyword": "보험 추천",
                    "titles": {
                        "naver_home": ["보험 추천", "보험 추천"],
                        "blog": ["보험 추천", "보험 추천"],
                    },
                }
            ],
            [
                {
                    "keyword": "보험 추천",
                    "titles": {
                        "naver_home": ["보험 추천 지금 비교할 포인트 2가지", "보험 추천 선택 기준 달라진 이유"],
                        "blog": ["보험 추천 완벽 정리", "보험 추천 비교 포인트 정리"],
                    },
                }
            ],
        ],
    ) as mocked_request:
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

    assert mocked_request.call_count == 2
    assert result["generation_meta"]["auto_retry"]["attempted_count"] == 1
    assert result["generation_meta"]["auto_retry"]["accepted_count"] == 1
    assert result["generated_titles"][0]["quality_report"]["retry_recommended"] is False
    assert result["generated_titles"][0]["quality_report"]["bundle_score"] >= 80
