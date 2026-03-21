from unittest.mock import patch

from app.title.ai_client import TitleGenerationOptions, _build_user_prompt_from_items, request_ai_titles
from app.title.category_detector import detect_category
from app.title.main import run
from app.title.rules import NAVER_HOME_MAX_LENGTH
from app.title.targets import build_title_targets
from app.title.title_generator import generate_titles
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


def test_title_generation_options_apply_preset_defaults() -> None:
    options = TitleGenerationOptions.from_input(
        {
            "title_options": {
                "mode": "ai",
                "preset_key": "openai_strict",
                "system_prompt": "숫자형 제목을 우선한다.",
            }
        }
    )

    assert options.preset_key == "openai_strict"
    assert options.preset_label == "안정형 규칙 우선"
    assert options.provider == "openai"
    assert options.model == "gpt-4.1-mini"
    assert options.temperature == 0.2
    assert "Preset guidance" in options.effective_system_prompt
    assert "Additional guidance" in options.effective_system_prompt


def test_title_generation_options_use_home_issue_preset_by_default_in_ai_mode() -> None:
    options = TitleGenerationOptions.from_input(
        {
            "title_options": {
                "mode": "ai",
            }
        }
    )

    assert options.preset_key == "openai_home_issue_safe"
    assert options.provider == "openai"
    assert options.model == "gpt-4.1-mini"
    assert options.temperature == 0.7
    assert options.issue_context_enabled is True
    assert options.issue_context_limit == 3
    assert "Naver home-feed exposure" in options.effective_system_prompt
    assert "When the issue signal is weak" in options.effective_system_prompt
    assert "Never invent unsupported facts" in options.effective_system_prompt


def test_ai_prompt_builder_includes_category_overlay_and_metrics() -> None:
    prompt = _build_user_prompt_from_items(
        [
            {
                "keyword": "서울 청약 경쟁률",
                "score": 77.0,
                "profitability_grade": "A",
                "attackability_grade": "2",
                "metrics": {
                    "volume": 1250.0,
                    "cpc": 310.0,
                },
                "target_mode": "single",
                "source_kind": "selected_keyword",
                "source_keywords": ["서울 청약 경쟁률", "서울 분양"],
                "source_note": "최근 청약 일정과 경쟁률 흐름 확인용",
                "issue_context": {
                    "fetched_at": "2026-03-21T08:00:00+09:00",
                    "title_count": 5,
                    "news_count": 2,
                    "source_mix": {"news": 2, "blog": 2, "official": 1},
                    "issue_terms": ["일정", "경쟁률", "분양"],
                    "news_headlines": [
                        "서울 청약 경쟁률 이번주 일정 바뀌나",
                        "서울 분양 경쟁률 다시 오르나",
                    ],
                },
            }
        ]
    )

    assert "Current local date reference:" in prompt
    assert "Never invent unsupported facts" in prompt
    assert "category overlay: 부동산 블로그" in prompt
    assert "preferred naver_home pair:" in prompt
    assert "freshness cues:" in prompt
    assert "data hooks:" in prompt
    assert "available signals: score 77" in prompt
    assert "grade A/2" in prompt
    assert "volume 1,250" in prompt
    assert "cpc 310" in prompt
    assert "target context: single" in prompt
    assert "source hints: selected_keyword" in prompt
    assert "source keywords 서울 청약 경쟁률, 서울 분양" in prompt
    assert "live issue context: fetched 2026-03-21 / news 2/5" in prompt
    assert "recent headlines: 서울 청약 경쟁률 이번주 일정 바뀌나" in prompt


def test_request_ai_titles_includes_live_issue_context_in_prompt() -> None:
    html = """
    <html>
      <body>
        <a href="https://news.example.com/a" class="news_tit">서울 청약 경쟁률 이번주 일정 바뀌나</a>
        <a href="https://blog.naver.com/post1" class="title_link">서울 청약 경쟁률 비교 포인트</a>
        <a href="https://news.example.com/b" class="news_tit">서울 분양 경쟁률 다시 오르나</a>
      </body>
    </html>
    """
    options = TitleGenerationOptions.from_input(
        {
            "title_options": {
                "mode": "ai",
                "provider": "openai",
                "api_key": "test-key",
                "issue_context_enabled": True,
                "issue_context_limit": 1,
            }
        }
    )

    with patch.dict("app.title.ai_client._ISSUE_CONTEXT_CACHE", {}, clear=True), patch(
        "app.title.ai_client.fetch_naver_serp_html",
        return_value=html,
    ), patch(
        "app.title.ai_client._request_openai_titles",
        return_value=[],
    ) as mocked_request:
        request_ai_titles([{"keyword": "서울 청약 경쟁률"}], options)

    prompt = mocked_request.call_args.args[0]
    assert "live issue context:" in prompt
    assert "recent headlines:" in prompt
    assert "서울 청약 경쟁률 이번주 일정 바뀌나" in prompt
    assert "news 2/3" in prompt


def test_title_generation_options_parse_quality_retry_settings() -> None:
    options = TitleGenerationOptions.from_input(
        {
            "title_options": {
                "mode": "ai",
                "auto_retry_enabled": False,
                "quality_retry_threshold": 92,
            }
        }
    )

    assert options.auto_retry_enabled is False
    assert options.quality_retry_threshold == 92


def test_title_generator_reports_preset_metadata() -> None:
    with patch(
        "app.title.title_generator.request_ai_titles",
        return_value=[
            {
                "keyword": "보험 추천",
                "titles": {
                    "naver_home": ["보험 추천 비교 포인트 2가지", "보험 추천 선택 기준 달라졌다"],
                    "blog": ["보험 추천 핵심 가이드", "보험 추천 체크 포인트 정리"],
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
                    "preset_key": "openai_balanced",
                    "api_key": "test-key",
                },
            }
        )

    assert result["generation_meta"]["preset_key"] == "openai_balanced"
    assert result["generation_meta"]["preset_label"] == "추천 균형형"
    assert result["generation_meta"]["provider"] == "openai"
    assert result["generation_meta"]["model"] == "gpt-4o-mini"
    assert result["generation_meta"]["temperature"] == 0.7


def test_title_generator_uses_custom_quality_retry_threshold_for_ai_titles() -> None:
    with patch(
        "app.title.title_generator.request_ai_titles",
        side_effect=[
            [
                {
                    "keyword": "보험 추천",
                    "titles": {
                        "naver_home": [
                            "지금 비교할 보험 추천 포인트 2가지",
                            "한눈에 보는 보험 추천 선택 기준",
                        ],
                        "blog": [
                            "실전 보험 추천 비교 가이드",
                            "지금 보는 보험 추천 체크리스트",
                        ],
                    },
                }
            ],
            [
                {
                    "keyword": "보험 추천",
                    "titles": {
                        "naver_home": [
                            "보험 추천 지금 비교할 포인트 2가지",
                            "보험 추천 선택 기준 한눈에 보기",
                        ],
                        "blog": [
                            "보험 추천 비교 가이드",
                            "보험 추천 체크리스트",
                        ],
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
                    "quality_retry_threshold": 95,
                },
            }
        )

    assert mocked_request.call_count == 2
    assert result["generation_meta"]["quality_retry_threshold"] == 95
    assert result["generation_meta"]["auto_retry"]["retry_threshold"] == 95
    assert result["generation_meta"]["auto_retry"]["attempted_count"] == 1
    assert result["generation_meta"]["auto_retry"]["accepted_count"] == 1
    assert result["generated_titles"][0]["quality_report"]["bundle_score"] >= 95


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


def test_title_generator_quality_retry_preserves_prompt_context() -> None:
    options = TitleGenerationOptions.from_input(
        {
            "title_options": {
                "mode": "ai",
                "provider": "openai",
                "api_key": "test-key",
                "model": "gpt-4.1-mini",
            }
        }
    )
    with patch(
        "app.title.title_generator.request_ai_titles",
        side_effect=[
            [
                {
                    "keyword": "서울 청약 경쟁률",
                    "titles": {
                        "naver_home": ["서울 청약 경쟁률", "서울 청약 경쟁률"],
                        "blog": ["서울 청약 경쟁률", "서울 청약 경쟁률"],
                    },
                }
            ],
            [
                {
                    "keyword": "서울 청약 경쟁률",
                    "titles": {
                        "naver_home": ["서울 청약 경쟁률 이번주 비교 포인트", "서울 청약 경쟁률 왜 달라졌나"],
                        "blog": ["서울 청약 경쟁률 체크포인트", "서울 청약 경쟁률 이슈 정리"],
                    },
                }
            ],
        ],
    ) as mocked_request:
        generate_titles(
            [
                {
                    "keyword": "서울 청약 경쟁률",
                    "score": 77.0,
                    "metrics": {"volume": 1250.0, "cpc": 310.0},
                    "source_kind": "selected_keyword",
                    "source_note": "최근 청약 일정과 경쟁률 흐름 확인용",
                    "source_keywords": ["서울 청약 경쟁률", "서울 분양"],
                }
            ],
            options=options,
        )

    assert mocked_request.call_count == 2
    retry_chunk = mocked_request.call_args_list[1].args[0]
    retry_options = mocked_request.call_args_list[1].kwargs["options"]

    assert retry_chunk[0]["keyword"] == "서울 청약 경쟁률"
    assert retry_chunk[0]["score"] == 77.0
    assert retry_chunk[0]["metrics"]["volume"] == 1250.0
    assert retry_chunk[0]["source_note"] == "최근 청약 일정과 경쟁률 흐름 확인용"
    assert "home-feed pair issue-aware" in retry_options.system_prompt
    assert "Do not invent unsupported dates, numbers, rankings, or official changes" in retry_options.system_prompt


def test_title_service_reuses_existing_serp_issue_context() -> None:
    with patch(
        "app.title.title_generator.request_ai_titles",
        return_value=[
            {
                "keyword": "보험 추천",
                "titles": {
                    "naver_home": ["보험 추천 이번주 비교 포인트", "보험 추천 기준 다시 보인다"],
                    "blog": ["보험 추천 체크포인트", "보험 추천 이슈 정리"],
                },
            }
        ],
    ) as mocked_request:
        run(
            {
                "selected_keywords": [
                    {
                        "keyword": "보험 추천",
                        "score": 1.0,
                    }
                ],
                "serp_competition_summary": {
                    "queries": [
                        {
                            "query": "보험 추천",
                            "source_mix": {"news": 1, "blog": 2},
                            "common_terms": ["비교", "기준"],
                            "top_titles": ["보험 추천 이번주 비교 포인트", "보험 추천 기준 바뀌었나"],
                        }
                    ]
                },
                "title_options": {
                    "mode": "ai",
                    "provider": "openai",
                    "api_key": "test-key",
                    "issue_context_enabled": False,
                },
            }
        )

    input_items = mocked_request.call_args.args[0]
    assert input_items[0]["issue_context"]["query"] == "보험 추천"
    assert input_items[0]["issue_context"]["source_mix"]["news"] == 1


def _build_longtail_title_input() -> dict:
    insurance = "\ubcf4\ud5d8 \ucd94\ucc9c"
    car_insurance = "\uc790\ub3d9\ucc28 \ubcf4\ud5d8"
    return {
        "selected_keywords": [
            {
                "keyword": insurance,
                "profitability_grade": "A",
                "attackability_grade": "2",
                "score": 76.0,
                "metrics": {"volume": 1200.0, "cpc": 210.0},
            },
            {
                "keyword": car_insurance,
                "profitability_grade": "B",
                "attackability_grade": "2",
                "score": 62.0,
                "metrics": {"volume": 900.0, "cpc": 180.0},
            },
        ],
        "keyword_clusters": [
            {
                "cluster_id": "cluster-01",
                "representative_keyword": insurance,
                "topic_terms": ["\ubcf4\ud5d8", "\ucd94\ucc9c", "\uac00\uc785"],
                "all_keywords": [insurance],
            },
            {
                "cluster_id": "cluster-02",
                "representative_keyword": car_insurance,
                "topic_terms": ["\uc790\ub3d9\ucc28", "\ubcf4\ud5d8", "\ud2b9\uc57d"],
                "all_keywords": [car_insurance],
            },
        ],
        "longtail_suggestions": [
            {
                "suggestion_id": "longtail-01",
                "cluster_id": "cluster-01",
                "representative_keyword": insurance,
                "source_keyword": "\ubcf4\ud5d8 \uac00\uc785 \uc870\uac74",
                "longtail_keyword": "\ubcf4\ud5d8 \uac00\uc785 \uc870\uac74 \uccb4\ud06c\ub9ac\uc2a4\ud2b8",
                "combination_terms": [insurance, "\ubcf4\ud5d8 \uac00\uc785 \uc870\uac74", "\uac00\uc785 \uc870\uac74"],
                "verification_status": "pass",
                "verified_score": 68.0,
            }
        ],
        "analyzed_keywords": [
            {
                "keyword": "\ubcf4\ud5d8 \uac00\uc785 \ubc29\ubc95",
                "score": 44.0,
                "metrics": {"volume": 180.0, "cpc": 120.0},
            },
            {
                "keyword": "\ubcf4\ud5d8 \uac00\uc785 \uc870\uac74",
                "score": 48.0,
                "metrics": {"volume": 220.0, "cpc": 135.0},
            },
            {
                "keyword": "\uc790\ub3d9\ucc28 \ubcf4\ud5d8 \ud2b9\uc57d \uc11c\ub958",
                "score": 20.0,
                "metrics": {"volume": 15.0, "cpc": 45.0},
            },
            {
                "keyword": "\uc790\ub3d9\ucc28 \ubcf4\ud5d8 \ud2b9\uc57d \uc815\ub9ac",
                "score": 12.0,
                "metrics": {"volume": 8.0, "cpc": 30.0},
            },
        ],
        "title_options": {
            "keyword_modes": [
                "single",
                "longtail_selected",
                "longtail_exploratory",
                "longtail_experimental",
            ]
        },
    }


def test_title_generator_builds_longtail_targets_for_keyword_modes() -> None:
    result = run(_build_longtail_title_input())

    summary = result["generation_meta"]["target_summary"]
    assert summary["requested_modes"] == [
        "single",
        "longtail_selected",
        "longtail_exploratory",
        "longtail_experimental",
    ]
    assert summary["mode_counts"]["single"] == 2
    assert summary["mode_counts"]["longtail_selected"] >= 1
    assert summary["mode_counts"]["longtail_exploratory"] >= 1
    assert summary["mode_counts"]["longtail_experimental"] >= 1
    assert len(result["generated_titles"]) == summary["target_count"]

    generated_modes = {item["target_mode"] for item in result["generated_titles"]}
    assert generated_modes == {
        "single",
        "longtail_selected",
        "longtail_exploratory",
        "longtail_experimental",
    }
    assert any(item["target_id"] for item in result["generated_titles"])
    assert any(
        item["base_keyword"] == "\uc790\ub3d9\ucc28 \ubcf4\ud5d8"
        for item in result["generated_titles"]
        if item["target_mode"] == "longtail_experimental"
    )


def test_title_generator_supports_explicit_title_targets() -> None:
    result = run(
        {
            "title_targets": [
                {
                    "target_id": "longtail_exploratory:insurance-checklist",
                    "keyword": "\ubcf4\ud5d8 \uac00\uc785 \uccb4\ud06c\ub9ac\uc2a4\ud2b8",
                    "target_mode": "longtail_exploratory",
                    "base_keyword": "\ubcf4\ud5d8 \ucd94\ucc9c",
                    "support_keywords": ["\ubcf4\ud5d8 \uac00\uc785"],
                    "source_keywords": ["\ubcf4\ud5d8 \ucd94\ucc9c", "\ubcf4\ud5d8 \uac00\uc785"],
                    "source_kind": "explicit_target",
                    "source_note": "\uc7ac\uc0dd\uc131 \uc804\uc6a9 target",
                }
            ],
            "title_options": {
                "mode": "template",
            },
        }
    )

    item = result["generated_titles"][0]
    assert item["target_id"].startswith("longtail_exploratory:")
    assert item["target_mode"] == "longtail_exploratory"
    assert item["base_keyword"] == "\ubcf4\ud5d8 \ucd94\ucc9c"
    assert item["support_keywords"] == ["\ubcf4\ud5d8 \uac00\uc785"]
    assert result["generation_meta"]["target_summary"]["requested_modes"] == ["longtail_exploratory"]


def test_title_generator_preserves_same_keyword_explicit_targets_across_modes() -> None:
    keyword = "\ubcf4\ud5d8 \uac00\uc785 \uccb4\ud06c\ub9ac\uc2a4\ud2b8"
    result = run(
        {
            "title_targets": [
                {
                    "target_id": "longtail_selected:insurance-checklist",
                    "keyword": keyword,
                    "target_mode": "longtail_selected",
                    "base_keyword": "\ubcf4\ud5d8 \ucd94\ucc9c",
                    "source_keywords": ["\ubcf4\ud5d8 \ucd94\ucc9c"],
                    "source_kind": "explicit_target",
                    "source_note": "V1",
                },
                {
                    "target_id": "longtail_exploratory:insurance-checklist",
                    "keyword": keyword,
                    "target_mode": "longtail_exploratory",
                    "base_keyword": "\ubcf4\ud5d8 \ucd94\ucc9c",
                    "source_keywords": ["\ubcf4\ud5d8 \ucd94\ucc9c"],
                    "source_kind": "explicit_target",
                    "source_note": "V2",
                },
            ],
            "title_options": {
                "mode": "template",
            },
        }
    )

    summary = result["generation_meta"]["target_summary"]
    assert summary["requested_modes"] == ["longtail_selected", "longtail_exploratory"]
    assert summary["mode_counts"]["longtail_selected"] == 1
    assert summary["mode_counts"]["longtail_exploratory"] == 1
    assert len(result["generated_titles"]) == 2
    assert {item["target_mode"] for item in result["generated_titles"]} == {
        "longtail_selected",
        "longtail_exploratory",
    }


def test_build_title_targets_related_modes_skip_self_derived_and_stopword_modifier_rows() -> None:
    items, summary = build_title_targets(
        {
            "selected_keywords": [
                {
                    "keyword": "\ubcf4\ud5d8 \ucd94\ucc9c",
                    "profitability_grade": "A",
                    "attackability_grade": "2",
                    "score": 76.0,
                    "metrics": {"volume": 1200.0, "cpc": 210.0},
                }
            ],
            "keyword_clusters": [
                {
                    "cluster_id": "cluster-01",
                    "representative_keyword": "\ubcf4\ud5d8 \ucd94\ucc9c",
                    "topic_terms": ["\ubcf4\ud5d8", "\ucd94\ucc9c", "\uac00\uc785"],
                    "all_keywords": ["\ubcf4\ud5d8 \ucd94\ucc9c"],
                }
            ],
            "analyzed_keywords": [
                {
                    "keyword": "\ubcf4\ud5d8 \uac00\uc785 \ubc29\ubc95",
                    "score": 44.0,
                    "metrics": {"volume": 180.0, "cpc": 120.0},
                },
                {
                    "keyword": "\ubcf4\ud5d8 \uac00\uc785 \uc870\uac74",
                    "score": 52.0,
                    "metrics": {"volume": 220.0, "cpc": 150.0},
                },
            ],
            "title_options": {
                "keyword_modes": ["longtail_exploratory"],
            },
        }
    )

    assert summary["mode_counts"]["longtail_exploratory"] == len(items)
    assert items
    assert all(item["target_mode"] == "longtail_exploratory" for item in items)
    assert all("\uc870\uac74" in item["keyword"] for item in items)
    assert all("\ucd94\ucc9c \uae30\uc900" not in item["keyword"] for item in items)
    assert all("\ubc29\ubc95 \uc804 \uccb4\ud06c\ud3ec\uc778\ud2b8" not in item["keyword"] for item in items)
