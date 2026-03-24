from unittest.mock import patch
import csv
import json
from pathlib import Path

from openpyxl import load_workbook

from app.title.ai_client import (
    TitleGenerationOptions,
    _build_user_prompt_from_items,
    _resolve_retry_delay_seconds,
    request_ai_titles,
)
from app.title.category_detector import detect_category
from app.title.main import run
from app.title.quality import assess_single_title, enrich_title_results
from app.title.rules import NAVER_HOME_MAX_LENGTH
from app.title.targets import _sanitize_related_mode_keyword, build_title_targets
from app.title.title_generator import _build_practical_rescue_item, generate_titles
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


def test_title_quality_accepts_keyword_tokens_with_inserted_modifiers() -> None:
    report = assess_single_title(
        "트레이더조 에코백 체크리스트",
        "트레이더조 에코백 구매 전 필수 체크리스트",
        "blog",
        {},
    )

    assert report["checks"]["contains_keyword"] is True
    assert report["checks"]["starts_with_keyword"] is True
    assert "키워드 핵심 표현이 제목에 충분히 반영되지 않았습니다." not in report["issues"]


def test_title_quality_still_fails_when_keyword_core_token_is_missing() -> None:
    report = assess_single_title(
        "트레이더조 에코백 체크리스트",
        "트레이더조 에코백 종류별 비교 가이드",
        "blog",
        {},
    )

    assert report["checks"]["contains_keyword"] is False
    assert "키워드 핵심 표현이 제목에 충분히 반영되지 않았습니다." in report["issues"]


def test_title_quality_flags_low_signal_generic_skeletons() -> None:
    report = assess_single_title(
        "로지텍 마우스",
        "로지텍 마우스 최신 정보",
        "blog",
        {},
    )

    assert "제목 골격이 템플릿형 표현에 머물러 있습니다." in report["issues"]
    assert report["checks"]["hard_reject_skeleton"] is True
    assert report["status"] == "retry"


def test_title_quality_rejects_vague_rank_and_best_question_frames() -> None:
    latest_rank = assess_single_title(
        "로지텍 마우스",
        "로지텍 마우스 최신 순위는?",
        "naver_home",
        {},
    )
    best_question = assess_single_title(
        "로지텍 마우스",
        "로지텍 마우스 뭐가 제일 좋을까",
        "naver_home",
        {},
    )

    assert latest_rank["checks"]["hard_reject_skeleton"] is True
    assert latest_rank["status"] == "retry"
    assert best_question["checks"]["hard_reject_skeleton"] is True
    assert best_question["status"] == "retry"


def test_title_quality_hard_rejects_generic_overlay_on_practical_keyword() -> None:
    report = assess_single_title(
        "로지텍 마우스 설정 팁",
        "로지텍 마우스 설정 팁 완벽 가이드",
        "blog",
        {},
    )

    assert "구체 글감 위에 다시 템플릿형 포장을 덧씌웠습니다." in report["issues"]
    assert report["checks"]["hard_reject_skeleton"] is True
    assert report["checks"]["generic_overlay_on_practical_keyword"] is True
    assert report["status"] == "retry"


def test_title_quality_allows_concrete_context_on_practical_keyword() -> None:
    report = assess_single_title(
        "MX Master 2S 연결 방법",
        "MX Master 2S 연결 방법 총정리 맥 M1 M2 포함",
        "blog",
        {},
    )

    assert report["checks"]["generic_overlay_on_practical_keyword"] is False


def test_title_quality_rejects_vague_teaser_and_reveal_frames() -> None:
    teaser = assess_single_title(
        "오사카 가성비 호텔",
        "오사카 가성비 호텔 숨은 보석 찾기",
        "blog",
        {},
    )
    reveal = assess_single_title(
        "무선 마우스 설정 팁 전 체크포인트",
        "무선 마우스 설정 팁 전 체크포인트 공개",
        "blog",
        {},
    )
    must_know = assess_single_title(
        "무선 마우스 설정 팁",
        "무선 마우스 설정 팁 꼭 알아둘 5가지",
        "blog",
        {},
    )

    assert teaser["checks"]["hard_reject_skeleton"] is True
    assert teaser["status"] == "retry"
    assert reveal["checks"]["hard_reject_skeleton"] is True
    assert reveal["status"] == "retry"
    assert must_know["checks"]["hard_reject_skeleton"] is True
    assert must_know["status"] == "retry"


def test_title_quality_retries_seed_anchor_single_without_concrete_intent_axis() -> None:
    enriched_items, _summary = enrich_title_results(
        [
            {
                "keyword": "닌텐도 스위치2 사전예약",
                "target_mode": "single",
                "source_selection_mode": "seed_anchor",
                "titles": {
                    "naver_home": [
                        "닌텐도 스위치2 사전예약, 이번주 시작?",
                        "닌텐도 스위치2 사전예약, 경쟁 치열할까",
                    ],
                    "blog": [
                        "닌텐도 스위치2 사전예약, 놓치면 후회할 핵심 정보",
                        "닌텐도 스위치2 사전예약, 구매 전 필독 체크리스트",
                    ],
                },
            }
        ]
    )

    report = enriched_items[0]["quality_report"]
    assert report["retry_recommended"] is True
    assert any("단일 키워드 제목이 의도 대비 너무 추상적이거나 낚시형입니다." in issue for issue in report["issues"])


def test_title_quality_retries_broad_product_single_with_hype_teaser_titles() -> None:
    enriched_items, _summary = enrich_title_results(
        [
            {
                "keyword": "로지텍 마우스",
                "target_mode": "single",
                "source_kind": "selected_keyword",
                "titles": {
                    "naver_home": [
                        "로지텍 마우스 신상, 이젠 이걸로 바꿔보세요",
                        "로지텍 마우스, 당신의 선택은?",
                    ],
                    "blog": [
                        "로지텍 마우스 최신 모델 비교 분석",
                        "로지텍 마우스, 왜 인기일까? 최신 트렌드 분석",
                    ],
                },
            }
        ]
    )

    report = enriched_items[0]["quality_report"]
    assert report["retry_recommended"] is True
    assert any("단일 키워드 제목이 의도 대비 너무 추상적이거나 낚시형입니다." in issue for issue in report["issues"])


def test_title_quality_retries_seed_anchor_value_single_without_concrete_stay_axes() -> None:
    enriched_items, _summary = enrich_title_results(
        [
            {
                "keyword": "오사카 가성비 호텔",
                "target_mode": "single",
                "source_selection_mode": "seed_anchor",
                "titles": {
                    "naver_home": [
                        "오사카 가성비 호텔, 이번주 특가 예약 팁",
                        "오사카 가성비 호텔, 숨겨진 혜택은?",
                    ],
                    "blog": [
                        "오사카 가성비 호텔, 2박 3일 예산별 추천",
                        "오사카 가성비 호텔, 예약부터 체크인까지 가이드",
                    ],
                },
            }
        ]
    )

    report = enriched_items[0]["quality_report"]
    assert report["retry_recommended"] is True
    assert report["recommended_pair_ready"] is False


def test_enrich_title_results_sorts_best_titles_first_for_output() -> None:
    enriched_items, _summary = enrich_title_results(
        [
            {
                "keyword": "로지텍 마우스",
                "target_mode": "single",
                "source_kind": "selected_keyword",
                "titles": {
                    "naver_home": [
                        "로지텍 마우스, 이번주 인기 순위는?",
                        "로지텍 마우스, 배터리와 연결 안정성",
                    ],
                    "blog": [
                        "로지텍 마우스 사용 후기",
                        "로지텍 마우스 배터리·연결 안정성·추천 대상 정리",
                    ],
                },
            }
        ]
    )

    item = enriched_items[0]
    assert item["titles"]["naver_home"][0] == "로지텍 마우스, 배터리와 연결 안정성"
    assert item["titles"]["blog"][0] == "로지텍 마우스 배터리·연결 안정성·추천 대상 정리"
    assert item["quality_report"]["title_checks"]["naver_home"][0]["status"] == "good"
    assert item["quality_report"]["title_checks"]["blog"][0]["status"] == "good"


def test_title_quality_retries_unverified_freshness_claim_without_issue_context() -> None:
    report = assess_single_title(
        "로지텍 마우스",
        "로지텍 마우스, 2주 실사용 후 장점은?",
        "naver_home",
        {},
        item_context={
            "keyword": "로지텍 마우스",
            "target_mode": "single",
            "source_kind": "selected_keyword",
        },
    )

    assert report["status"] == "retry"
    assert report["checks"]["unverified_freshness_claim"] is True


def test_title_quality_allows_freshness_claim_when_issue_context_exists() -> None:
    report = assess_single_title(
        "서울 청약 경쟁률",
        "서울 청약 경쟁률, 이번주 일정 바뀌나",
        "naver_home",
        {},
        item_context={
            "keyword": "서울 청약 경쟁률",
            "target_mode": "single",
            "issue_context": {
                "query": "서울 청약 경쟁률",
                "title_count": 1,
            },
        },
    )

    assert report["checks"]["unverified_freshness_claim"] is False


def test_title_quality_normalizes_colon_style_and_flags_it() -> None:
    report = assess_single_title(
        "로지텍 마우스",
        "로지텍 마우스：장단점 정리",
        "naver_home",
        {},
    )

    assert ":" not in report["title"]
    assert "：" not in report["title"]
    assert report["checks"]["forbidden_punctuation_used"] is True


def test_enrich_title_results_strips_colons_from_output_titles() -> None:
    enriched_items, _ = enrich_title_results(
        [
            {
                "keyword": "닌텐도 스위치2 사전예약",
                "titles": {
                    "naver_home": [
                        "닌텐도 스위치2 사전예약：오픈 시간 확인",
                        "닌텐도 스위치2 사전예약:결제 조건 확인",
                    ],
                    "blog": [
                        "닌텐도 스위치2 사전예약：오픈 시간·결제 조건 정리",
                        "닌텐도 스위치2 사전예약:수령 일정과 인증 정리",
                    ],
                },
            }
        ]
    )

    item = enriched_items[0]
    assert all(":" not in title and "：" not in title for title in item["titles"]["naver_home"])
    assert all(":" not in title and "：" not in title for title in item["titles"]["blog"])


def test_title_quality_keeps_specific_editorial_product_frame() -> None:
    report = assess_single_title(
        "로지텍 마우스",
        "로지텍 마우스 실사용 장단점과 클릭감 차이",
        "blog",
        {},
    )

    assert "제목 골격이 너무 일반적입니다." not in report["issues"]
    assert report["status"] in {"good", "review"}


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


def test_template_titles_expand_intent_detection_for_value_and_setting_keywords() -> None:
    value_titles = build_blog_titles("오사카 가성비 호텔", "general")
    setting_titles = build_blog_titles("무선 마우스 설정 팁", "general")

    assert any(("기준" in title or "선택" in title or "차이" in title) for title in value_titles)
    assert any(("준비" in title or "절차" in title or "설정" in title or "포인트" in title) for title in setting_titles)


def test_template_titles_avoid_repeating_noisy_checklist_and_guide_frames() -> None:
    blog_titles = build_blog_titles("로지텍 마우스", "general")
    noisy_titles = [
        title
        for title in blog_titles
        if any(term in title for term in ("체크리스트", "체크포인트", "가이드", "비교 가이드"))
    ]

    assert len(blog_titles) == 2
    assert len(noisy_titles) <= 1


def test_title_quality_marks_batch_level_repeated_headline_skeletons_for_retry() -> None:
    repeated_batch = [
        {
            "keyword": "로지텍 마우스",
            "titles": {
                "naver_home": ["로지텍 마우스 뭐가 다를까", "로지텍 마우스 추천 기준"],
                "blog": ["로지텍 마우스 체크리스트", "로지텍 마우스 비교 포인트"],
            },
        },
        {
            "keyword": "레이저 마우스",
            "titles": {
                "naver_home": ["레이저 마우스 뭐가 다를까", "레이저 마우스 추천 기준"],
                "blog": ["레이저 마우스 체크리스트", "레이저 마우스 비교 포인트"],
            },
        },
        {
            "keyword": "앱코 마우스",
            "titles": {
                "naver_home": ["앱코 마우스 뭐가 다를까", "앱코 마우스 추천 기준"],
                "blog": ["앱코 마우스 체크리스트", "앱코 마우스 비교 포인트"],
            },
        },
    ]

    enriched_items, summary = enrich_title_results(repeated_batch)
    report = enriched_items[0]["quality_report"]

    assert report["retry_recommended"] is True
    assert report["batch_repeat_risk"] is True
    assert any("뭐가 다를까" in issue for issue in report["issues"])
    assert any("추천 기준" in issue for issue in report["issues"])
    assert report["title_checks"]["naver_home"][0]["checks"]["batch_repeat_risk"] is True
    assert summary["retry_count"] == 3


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
                    "keyword_modes": ["single"],
                },
            }
        )

    assert result["generation_meta"]["used_mode"] == "ai"
    assert result["generation_meta"]["provider"] == "openai"
    assert result["generation_meta"]["auto_retry"]["accepted_count"] == 0
    assert result["generation_meta"]["auto_retry"]["attempted_count"] == 0
    assert "완벽 가이드" not in result["generated_titles"][0]["titles"]["blog"][0]
    assert "보험 추천 비교 포인트 정리" == result["generated_titles"][0]["titles"]["blog"][0]
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


def test_title_generator_exports_csv_by_default_when_enabled(tmp_path: Path) -> None:
    result = run(
        {
            "category": "비즈니스경제",
            "seed_input": "보험 추천",
            "selected_keywords": [
                {
                    "keyword": "보험 추천",
                    "score": 1.0,
                }
            ],
            "title_export": {
                "enabled": True,
                "output_dir": str(tmp_path),
            },
        }
    )

    export_artifact = result["generation_meta"]["export_artifact"]
    artifact_path = Path(export_artifact["path"])
    assert artifact_path.exists()
    assert artifact_path.suffix == ".csv"
    assert artifact_path.parent.name == "csv"
    assert export_artifact["category"] == "비즈니스경제"
    assert export_artifact["seed_keyword"] == "보험 추천"
    export_artifacts = result["generation_meta"]["export_artifacts"]
    assert [item["format"] for item in export_artifacts] == ["csv"]
    assert all(Path(item["path"]).exists() for item in export_artifacts)

    with artifact_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))

    assert rows[0] == [
        "keyword",
        "duplicate",
        "recent_used_date",
        "naver_home_1",
        "naver_home_2",
        "blog_1",
        "blog_2",
    ]
    assert rows[1][0] == "보험 추천"


def test_title_generator_can_export_multiple_formats_when_requested(tmp_path: Path) -> None:
    result = run(
        {
            "category": "비즈니스경제",
            "seed_input": "보험 추천",
            "selected_keywords": [
                {
                    "keyword": "보험 추천",
                    "score": 1.0,
                }
            ],
            "title_export": {
                "enabled": True,
                "output_dir": str(tmp_path),
                "formats": ["csv", "xlsx", "md"],
            },
        }
    )

    export_artifacts = result["generation_meta"]["export_artifacts"]
    assert [item["format"] for item in export_artifacts] == ["csv", "xlsx", "md"]

    workbook_path = next(Path(item["path"]) for item in export_artifacts if item["format"] == "xlsx")
    workbook = load_workbook(workbook_path)
    assert workbook.sheetnames == ["summary", "titles"]
    assert workbook["titles"]["A2"].value == "보험 추천"

    markdown_path = next(Path(item["path"]) for item in export_artifacts if item["format"] == "md")
    markdown_text = markdown_path.read_text(encoding="utf-8")
    assert "# Title Export" in markdown_text
    assert "## 보험 추천" in markdown_text


def test_title_generator_can_export_queue_txt_bundle_with_manifest(tmp_path: Path) -> None:
    result = run(
        {
            "category": "비즈니스경제",
            "seed_input": "보험 추천",
            "selected_keywords": [
                {
                    "keyword": "보험 추천",
                    "score": 1.0,
                }
            ],
            "title_export": {
                "enabled": True,
                "output_dir": str(tmp_path),
                "queue_export": {
                    "enabled": True,
                    "destination": "wordpress",
                    "topic": "보험",
                },
            },
        }
    )

    export_artifacts = result["generation_meta"]["export_artifacts"]
    artifact_paths = {item["format"]: Path(item["path"]) for item in export_artifacts}
    assert "txt_live" in artifact_paths
    assert "txt_archive" in artifact_paths
    assert "manifest_json" in artifact_paths
    assert result["generation_meta"]["queue_export"]["destination"] == "wordpress"
    assert artifact_paths["txt_live"].parent.name == "wordpress"
    assert artifact_paths["txt_live"].read_text(encoding="utf-8").strip()
    selected_title = result["generated_titles"][0]["titles"]["blog"][0]
    assert selected_title in artifact_paths["txt_live"].read_text(encoding="utf-8")
    manifest_payload = json.loads(artifact_paths["manifest_json"].read_text(encoding="utf-8"))
    assert manifest_payload["destination"] == "wordpress"
    assert manifest_payload["topic"] == "보험"
    assert manifest_payload["entries"][0]["selected_title"] == selected_title


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
    assert options.issue_source_mode == "mixed"
    assert "Preset guidance" in options.effective_system_prompt
    assert "Additional guidance" in options.effective_system_prompt


def test_title_generation_options_use_mixed_stable_preset_by_default_in_ai_mode() -> None:
    options = TitleGenerationOptions.from_input(
        {
            "title_options": {
                "mode": "ai",
            }
        }
    )

    assert options.preset_key == "openai_mixed_stable"
    assert options.provider == "openai"
    assert options.model == "gpt-4.1-mini"
    assert options.temperature == 0.5
    assert options.issue_context_enabled is True
    assert options.issue_context_limit == 3
    assert options.issue_source_mode == "mixed"
    assert options.community_sources == ("cafe.naver.com", "blog.naver.com", "post.naver.com")
    assert "mixed issue sourcing as the default operating mode" in options.effective_system_prompt
    assert "community reaction cues" in options.effective_system_prompt


def test_title_generation_options_apply_reaction_aggressive_preset_defaults() -> None:
    options = TitleGenerationOptions.from_input(
        {
            "title_options": {
                "mode": "ai",
                "preset_key": "openai_reaction_aggressive",
            }
        }
    )

    assert options.preset_key == "openai_reaction_aggressive"
    assert options.provider == "openai"
    assert options.model == "gpt-4.1-mini"
    assert options.temperature == 0.8
    assert options.issue_source_mode == "reaction"
    assert options.community_sources == ("cafe.naver.com", "blog.naver.com", "post.naver.com")
    assert "Prioritize selected-domain community reaction cues" in options.effective_system_prompt


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
    assert "Every title must contain all meaningful keyword tokens from the input keyword." in prompt
    assert "Keep keyword tokens in the same order." in prompt
    assert "category overlay: 부동산 블로그" in prompt
    assert "preferred naver_home pair:" in prompt
    assert "freshness cues:" in prompt
    assert "data hooks:" in prompt
    assert "required keyword tokens: 서울, 청약, 경쟁률" in prompt
    assert "keyword coverage rule:" in prompt
    assert "available signals: score 77" in prompt
    assert "grade A/2" in prompt
    assert "volume 1,250" in prompt
    assert "cpc 310" in prompt
    assert "target context: single" in prompt
    assert "source hints: selected_keyword" in prompt
    assert "source keywords 서울 청약 경쟁률, 서울 분양" in prompt
    assert "live issue context: mode mixed / fetched 2026-03-21 / news 2/5" in prompt
    assert "recent headlines: 서울 청약 경쟁률 이번주 일정 바뀌나" in prompt


def test_ai_prompt_builder_includes_practical_title_shape_hint() -> None:
    prompt = _build_user_prompt_from_items(
        [
            {
                "keyword": "로지텍 마우스 설정 팁",
                "target_mode": "longtail_selected",
            }
        ]
    )

    assert "practical title shape: setup/help" in prompt
    assert "device or OS context" in prompt


def test_ai_prompt_builder_expands_preorder_and_value_hints() -> None:
    prompt = _build_user_prompt_from_items(
        [
            {
                "keyword": "닌텐도 스위치2 사전예약",
                "target_mode": "single",
                "source_selection_mode": "seed_anchor",
                "source_selection_reason": "seed_intent_preserved",
            },
            {
                "keyword": "오사카 가성비 호텔",
                "target_mode": "single",
                "source_selection_mode": "seed_anchor",
            },
        ]
    )

    assert "practical title shape: preorder/application" in prompt
    assert "practical title shape: value decision" in prompt
    assert "source hints: selected_keyword / selection seed_anchor" not in prompt
    assert "selection seed_anchor" in prompt
    assert "selection note seed_intent_preserved" in prompt


def test_ai_prompt_builder_warns_against_keyword_shortening() -> None:
    prompt = _build_user_prompt_from_items(
        [
            {
                "keyword": "손목 편한 마우스 설정 팁",
                "target_mode": "longtail_selected",
            }
        ]
    )

    assert "Do not shorten the keyword phrase" in prompt


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
    assert "required keyword tokens: 서울, 청약, 경쟁률" in prompt


def test_request_ai_titles_includes_selected_community_reaction_in_prompt() -> None:
    html = """
    <html>
      <body>
        <a href="https://news.example.com/a" class="news_tit">보험 추천 이번주 비교 포인트</a>
        <a href="https://cafe.naver.com/post1" class="title_link">보험 추천 후기 비교 포인트</a>
        <a href="https://blog.naver.com/post2" class="title_link">보험 추천 가입 조건 정리</a>
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
                "issue_source_mode": "reaction",
                "community_sources": ["cafe_naver"],
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
        request_ai_titles([{"keyword": "보험 추천"}], options)

    prompt = mocked_request.call_args.args[0]
    assert "community reaction:" in prompt
    assert "community headlines:" in prompt
    assert "후기" in prompt
    assert "보험 추천 후기 비교 포인트" in prompt


def test_request_ai_titles_supports_vertex_provider() -> None:
    options = TitleGenerationOptions.from_input(
        {
            "title_options": {
                "mode": "ai",
                "provider": "vertex",
                "api_key": "vertex-key",
                "model": "gemini-2.5-flash-lite",
            }
        }
    )

    with patch(
        "app.title.ai_client._post_json",
        return_value={
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": (
                                    '{"items":[{"keyword":"보험 추천","naver_home":["보험 추천 비교 포인트","보험 추천 선택 기준"],'
                                    '"blog":["보험 추천 가이드","보험 추천 체크포인트"]}]}'
                                )
                            }
                        ]
                    }
                }
            ]
        },
    ) as mocked_post:
        result = request_ai_titles([{"keyword": "보험 추천"}], options)

    called_url = mocked_post.call_args.args[0]
    called_headers = mocked_post.call_args.args[1]
    assert "aiplatform.googleapis.com" in called_url
    assert "publishers/google/models/gemini-2.5-flash-lite:generateContent" in called_url
    assert "key=vertex-key" in called_url
    assert called_headers["Content-Type"] == "application/json"
    assert result[0]["keyword"] == "보험 추천"


def test_resolve_retry_delay_seconds_reads_provider_hint() -> None:
    delay = _resolve_retry_delay_seconds(
        "429 You exceeded your current quota. Please retry in 44.460159992s.",
        attempt=0,
    )

    assert delay == 44.460159992


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


def test_title_generator_keeps_custom_quality_retry_threshold_without_extra_retry_when_pair_ready() -> None:
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

    assert mocked_request.call_count == 1
    assert result["generation_meta"]["quality_retry_threshold"] == 95
    assert result["generation_meta"]["auto_retry"]["retry_threshold"] == 95
    assert result["generation_meta"]["auto_retry"]["attempted_count"] == 0
    assert result["generation_meta"]["auto_retry"]["accepted_count"] == 0
    assert result["generated_titles"][0]["quality_report"]["recommended_pair_ready"] is True


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


def test_title_generator_skips_auto_retry_when_recommended_pair_is_already_ready() -> None:
    with patch(
        "app.title.title_generator.request_ai_titles",
        return_value=[
            {
                "keyword": "로지텍 마우스",
                "titles": {
                    "naver_home": [
                        "로지텍 마우스, 이번주 인기 순위는?",
                        "로지텍 마우스, 배터리와 연결 안정성",
                    ],
                    "blog": [
                        "로지텍 마우스 사용 후기",
                        "로지텍 마우스 배터리·연결 안정성·추천 대상 정리",
                    ],
                },
            }
        ],
    ) as mocked_request:
        result = run(
            {
                "selected_keywords": [
                    {
                        "keyword": "로지텍 마우스",
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

    report = result["generated_titles"][0]["quality_report"]
    assert mocked_request.call_count == 1
    assert report["recommended_pair_ready"] is True
    assert report["status"] == "review"
    assert result["generation_meta"]["auto_retry"]["attempted_count"] == 0
    assert result["generation_meta"]["auto_retry"]["accepted_count"] == 0


def test_title_generator_practical_rescue_keeps_full_keyword_after_failed_retries() -> None:
    keyword = "손목 편한 마우스 설정 팁"

    with patch(
        "app.title.title_generator.request_ai_titles",
        side_effect=[
            [
                {
                    "keyword": keyword,
                    "titles": {
                        "naver_home": [
                            "편한 마우스 설정 팁, 최신 정보",
                            "편한 마우스 설정 팁, 뭐가 다를까?",
                        ],
                        "blog": [
                            "편한 마우스 설정 팁 총정리",
                            "편한 마우스 설정 팁 완벽 가이드",
                        ],
                    },
                }
            ],
            [
                {
                    "keyword": keyword,
                    "titles": {
                        "naver_home": [
                            "편한 마우스 설정 팁, 최신 비교 분석",
                            "편한 마우스 설정 팁, 이것만 알면",
                        ],
                        "blog": [
                            "편한 마우스 설정 팁 최신 정보",
                            "편한 마우스 설정 팁 구매 가이드",
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
                        "keyword": keyword,
                        "score": 1.0,
                    }
                ],
                "title_options": {
                    "mode": "ai",
                    "provider": "openai",
                    "api_key": "test-key",
                    "model": "gpt-4o-mini",
                    "keyword_modes": ["single"],
                },
            }
        )

    item = result["generated_titles"][0]
    all_titles = item["titles"]["naver_home"] + item["titles"]["blog"]

    assert mocked_request.call_count == 2
    assert result["generation_meta"]["auto_retry"]["attempted_count"] == 1
    assert result["generation_meta"]["auto_retry"]["accepted_count"] == 1
    assert result["generation_meta"]["model_escalation"]["triggered"] is False
    assert item["quality_report"]["retry_recommended"] is False
    assert item["quality_report"]["bundle_score"] >= 84
    assert all(keyword in title for title in all_titles)
    assert all(
        banned not in title
        for title in all_titles
        for banned in (
            "최신 정보",
            "최신 비교 분석",
            "총정리",
            "완벽 가이드",
            "뭐가 다를까",
            "이것만 알면",
            "구매 가이드",
        )
    )


def test_practical_rescue_stays_generic_for_non_product_setting_keyword() -> None:
    item = _build_practical_rescue_item({"keyword": "전세 계약 설정 팁"})

    assert item is not None
    all_titles = item["titles"]["naver_home"] + item["titles"]["blog"]
    assert all("블루투스" not in title for title in all_titles)
    assert all("DPI" not in title for title in all_titles)
    assert all("버튼" not in title for title in all_titles)


def test_practical_rescue_uses_keyboard_specific_setting_frames_without_dpi() -> None:
    item = _build_practical_rescue_item({"keyword": "아콘 키보드 설정 팁"})

    assert item is not None
    all_titles = item["titles"]["naver_home"] + item["titles"]["blog"]
    assert all("DPI" not in title for title in all_titles)
    assert any(
        any(term in title for term in ("멀티페어링", "키맵", "한영", "FN Lock", "배열"))
        for title in all_titles
    )


def test_practical_rescue_detects_preorder_keywords_without_generic_wrappers() -> None:
    item = _build_practical_rescue_item({"keyword": "로지텍 지슈스 사전예약"})

    assert item is not None
    all_titles = item["titles"]["naver_home"] + item["titles"]["blog"]
    assert all("로지텍 지슈스 사전예약" in title for title in all_titles)
    assert all(
        banned not in title
        for title in all_titles
        for banned in ("총정리", "최신 정보", "구매 가이드", "놓치면 후회", "지금 신청?")
    )
    assert any("일정" in title or "신청" in title or "혜택" in title for title in all_titles)


def test_practical_rescue_problem_keywords_rotate_across_more_than_one_frame() -> None:
    first = _build_practical_rescue_item({"keyword": "로지텍 슈퍼스트라이크 자주 생기는 문제"})
    second = _build_practical_rescue_item({"keyword": "로지텍 지슈라 스트라이크 자주 생기는 문제"})

    assert first is not None
    assert second is not None
    assert first["titles"]["naver_home"] != second["titles"]["naver_home"]
    assert first["titles"]["blog"] != second["titles"]["blog"]


def test_practical_rescue_adds_concrete_value_frames_for_seed_anchor_keyword() -> None:
    item = _build_practical_rescue_item(
        {
            "keyword": "오사카 가성비 호텔",
            "target_mode": "single",
            "source_selection_mode": "seed_anchor",
        }
    )

    assert item is not None
    all_titles = item["titles"]["naver_home"] + item["titles"]["blog"]
    assert all("오사카 가성비 호텔" in title for title in all_titles)
    assert any(
        any(term in title for term in ("위치", "교통", "추가요금", "예산", "조식", "취소"))
        for title in all_titles
    )
    assert all(
        banned not in title
        for title in all_titles
        for banned in ("숨은 보석", "찾아봐요", "최신 정보")
    )


def test_practical_rescue_specializes_preorder_single_and_checkpoint_variants() -> None:
    single = _build_practical_rescue_item(
        {
            "keyword": "닌텐도 스위치2 사전예약",
            "target_mode": "single",
            "source_selection_mode": "seed_anchor",
        }
    )
    checkpoint = _build_practical_rescue_item(
        {
            "keyword": "닌텐도 스위치2 사전예약 전 체크포인트",
            "target_mode": "longtail_selected",
            "source_selection_mode": "seed_anchor",
        }
    )

    assert single is not None
    assert checkpoint is not None
    single_titles = single["titles"]["naver_home"] + single["titles"]["blog"]
    checkpoint_titles = checkpoint["titles"]["naver_home"] + checkpoint["titles"]["blog"]
    assert single["titles"]["naver_home"] != checkpoint["titles"]["naver_home"]
    assert any(
        any(term in title for term in ("신청 링크", "카드 혜택", "오픈 일정", "결제 수단", "수령 일정"))
        for title in single_titles
    )
    assert any(
        any(term in title for term in ("본인 인증", "제한 수량", "결제 조건", "접속 시간", "수령 일정"))
        for title in checkpoint_titles
    )


def test_practical_rescue_builds_concrete_generic_product_single_titles() -> None:
    item = _build_practical_rescue_item(
        {
            "keyword": "로지텍 마우스",
            "target_mode": "single",
            "source_kind": "selected_keyword",
        }
    )

    assert item is not None
    all_titles = item["titles"]["naver_home"] + item["titles"]["blog"]
    assert any(
        any(term in title for term in ("실사용", "장단점", "가격대", "추천 대상", "클릭감", "배터리"))
        for title in all_titles
    )
    assert all(
        banned not in title
        for title in all_titles
        for banned in ("당신의 선택", "왜 인기", "신상", "트렌드 분석")
    )


def test_practical_rescue_builds_concrete_generic_stay_single_titles() -> None:
    item = _build_practical_rescue_item(
        {
            "keyword": "오사카 호텔",
            "target_mode": "single",
            "source_kind": "selected_keyword",
        }
    )

    assert item is not None
    all_titles = item["titles"]["naver_home"] + item["titles"]["blog"]
    assert any(
        any(term in title for term in ("위치", "교통", "추가요금", "객실", "조식", "취소"))
        for title in all_titles
    )


def test_title_generator_escalates_model_after_two_failed_quality_attempts() -> None:
    """
    with patch(
        "app.title.title_generator.request_ai_titles",
        side_effect=[
            [
                {
                    "keyword": "蹂댄뿕 異붿쿇",
                    "titles": {
                        "naver_home": ["蹂댄뿕 異붿쿇", "蹂댄뿕 異붿쿇"],
                        "blog": ["蹂댄뿕 異붿쿇", "蹂댄뿕 異붿쿇"],
                    },
                }
            ],
            [
                {
                    "keyword": "蹂댄뿕 異붿쿇",
                    "titles": {
                        "naver_home": ["蹂댄뿕 異붿쿇 鍮꾧탳", "蹂댄뿕 異붿쿇 鍮꾧탳"],
                        "blog": ["蹂댄뿕 異붿쿇 媛?대뱶", "蹂댄뿕 異붿쿇 媛?대뱶"],
                    },
                }
            ],
            [
                {
                    "keyword": "蹂댄뿕 異붿쿇",
                    "titles": {
                        "naver_home": [
                            "蹂댄뿕 異붿쿇 吏湲?鍮꾧탳 ?ъ씤??2媛吏",
                            "蹂댄뿕 異붿쿇 ?좏깮 湲곗? ?щ씪吏??댁쑀",
                        ],
                        "blog": [
                            "蹂댄뿕 異붿쿇 鍮꾧탳 媛?대뱶",
                            "蹂댄뿕 異붿쿇 泥댄겕由ъ뒪??,
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
                        "keyword": "蹂댄뿕 異붿쿇",
                        "score": 1.0,
                    }
                ],
                "title_options": {
                    "mode": "ai",
                    "provider": "openai",
                    "api_key": "test-key",
                    "model": "gpt-4o-mini",
                    "keyword_modes": ["single"],
                },
            }
        )

    assert mocked_request.call_count == 3
    assert mocked_request.call_args_list[0].kwargs["options"].model == "gpt-4o-mini"
    assert mocked_request.call_args_list[1].kwargs["options"].model == "gpt-4o-mini"
    assert mocked_request.call_args_list[2].kwargs["options"].model == "gpt-4.1-mini"
    assert result["generation_meta"]["auto_retry"]["attempted_count"] == 1
    assert result["generation_meta"]["auto_retry"]["accepted_count"] == 0
    assert result["generation_meta"]["model_escalation"]["enabled"] is True
    assert result["generation_meta"]["model_escalation"]["triggered"] is True
    assert result["generation_meta"]["model_escalation"]["source_model"] == "gpt-4o-mini"
    assert result["generation_meta"]["model_escalation"]["target_model"] == "gpt-4.1-mini"
    assert result["generation_meta"]["model_escalation"]["attempted_count"] == 1
    assert result["generation_meta"]["model_escalation"]["accepted_count"] == 1
    assert result["generation_meta"]["final_model"] == "gpt-4.1-mini"
    assert result["generated_titles"][0]["quality_report"]["retry_recommended"] is False
    assert result["generated_titles"][0]["quality_report"]["bundle_score"] >= 84
    """

    keyword = "insurance plan"

    with patch(
        "app.title.title_generator.request_ai_titles",
        side_effect=[
            [
                {
                    "keyword": keyword,
                    "titles": {
                        "naver_home": [keyword, keyword],
                        "blog": [keyword, keyword],
                    },
                }
            ],
            [
                {
                    "keyword": keyword,
                    "titles": {
                        "naver_home": [f"{keyword}!!", f"{keyword}!!"],
                        "blog": [f"{keyword}!!", f"{keyword}!!"],
                    },
                }
            ],
            [
                {
                    "keyword": keyword,
                    "titles": {
                        "naver_home": [
                            f"{keyword} compare 2 options",
                            f"{keyword} choice checklist",
                        ],
                        "blog": [
                            f"{keyword} compare guide",
                            f"{keyword} signup checklist",
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
                        "keyword": keyword,
                        "score": 1.0,
                    }
                ],
                "title_options": {
                    "mode": "ai",
                    "provider": "openai",
                    "api_key": "test-key",
                    "model": "gpt-4o-mini",
                    "keyword_modes": ["single"],
                },
            }
        )

    assert mocked_request.call_count == 3
    assert mocked_request.call_args_list[0].kwargs["options"].model == "gpt-4o-mini"
    assert mocked_request.call_args_list[1].kwargs["options"].model == "gpt-4o-mini"
    assert mocked_request.call_args_list[2].kwargs["options"].model == "gpt-4.1-mini"
    assert result["generation_meta"]["auto_retry"]["attempted_count"] == 1
    assert result["generation_meta"]["auto_retry"]["accepted_count"] == 0
    assert result["generation_meta"]["model_escalation"]["enabled"] is True
    assert result["generation_meta"]["model_escalation"]["triggered"] is True
    assert result["generation_meta"]["model_escalation"]["source_model"] == "gpt-4o-mini"
    assert result["generation_meta"]["model_escalation"]["target_model"] == "gpt-4.1-mini"
    assert result["generation_meta"]["model_escalation"]["attempted_count"] == 1
    assert result["generation_meta"]["model_escalation"]["accepted_count"] == 1
    assert result["generation_meta"]["final_model"] == "gpt-4.1-mini"
    assert result["generated_titles"][0]["quality_report"]["retry_recommended"] is False
    assert result["generated_titles"][0]["quality_report"]["bundle_score"] >= 84


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
        "longtail_options": {
            "optional_suffix_keys": ["guide", "checklist"],
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
    assert summary["mode_counts"]["longtail_experimental"] >= 0
    assert len(result["generated_titles"]) == summary["target_count"]

    generated_modes = {item["target_mode"] for item in result["generated_titles"]}
    assert {"single", "longtail_selected", "longtail_exploratory"}.issubset(generated_modes)
    assert any(item["target_id"] for item in result["generated_titles"])
    if summary["mode_counts"]["longtail_experimental"] >= 1:
        assert any(
            item["base_keyword"] == "\uc790\ub3d9\ucc28 \ubcf4\ud5d8"
            for item in result["generated_titles"]
            if item["target_mode"] == "longtail_experimental"
        )


def test_build_title_targets_defaults_to_single_and_v1_modes() -> None:
    items, summary = build_title_targets(
        {
            "selected_keywords": [
                {
                    "keyword": "\ubcf4\ud5d8 \ucd94\ucc9c",
                    "score": 76.0,
                    "metrics": {"volume": 1200.0, "cpc": 210.0},
                }
            ],
            "keyword_clusters": [
                {
                    "cluster_id": "cluster-01",
                    "representative_keyword": "\ubcf4\ud5d8 \ucd94\ucc9c",
                    "topic_terms": ["\ubcf4\ud5d8", "\ucd94\ucc9c", "\uac00\uc785"],
                    "all_keywords": ["\ubcf4\ud5d8 \ucd94\ucc9c", "\ubcf4\ud5d8 \uac00\uc785 \uccb4\ud06c\ub9ac\uc2a4\ud2b8"],
                }
            ],
            "longtail_suggestions": [
                {
                    "suggestion_id": "longtail-01",
                    "representative_keyword": "\ubcf4\ud5d8 \ucd94\ucc9c",
                    "longtail_keyword": "\ubcf4\ud5d8 \uac00\uc785 \uccb4\ud06c\ub9ac\uc2a4\ud2b8",
                    "verification_status": "pass",
                    "verified_score": 68.0,
                }
            ],
        }
    )

    assert summary["requested_modes"] == ["single", "longtail_selected"]
    assert summary["mode_counts"]["single"] == 1
    assert summary["mode_counts"]["longtail_selected"] == 1
    assert {item["target_mode"] for item in items} == {"single", "longtail_selected"}


def test_build_title_targets_rewrites_low_signal_longtail_keywords() -> None:
    items, summary = build_title_targets(
        {
            "selected_keywords": [
                {
                    "keyword": "로지텍 마우스",
                    "score": 76.0,
                    "metrics": {"volume": 1200.0, "cpc": 210.0},
                }
            ],
            "keyword_clusters": [
                {
                    "cluster_id": "cluster-01",
                    "representative_keyword": "로지텍 마우스",
                    "topic_terms": ["로지텍", "마우스"],
                    "all_keywords": ["로지텍 마우스"],
                }
            ],
            "longtail_suggestions": [
                {
                    "suggestion_id": "longtail-01",
                    "representative_keyword": "로지텍 마우스",
                    "longtail_keyword": "로지텍 마우스 추천 기준",
                    "verification_status": "pass",
                    "verified_score": 71.0,
                },
                {
                    "suggestion_id": "longtail-02",
                    "representative_keyword": "로지텍 마우스",
                    "longtail_keyword": "로지텍 마우스 연결 방법",
                    "verification_status": "pass",
                    "verified_score": 69.0,
                },
            ],
        }
    )

    keywords = {item["keyword"] for item in items}

    assert "로지텍 마우스 추천 기준" not in keywords
    assert any(keyword in keywords for keyword in ("로지텍 마우스 실사용 차이", "로지텍 마우스 장단점"))
    assert "로지텍 마우스 연결 방법" in keywords
    assert summary["mode_counts"]["longtail_selected"] == 2


def test_build_title_targets_limits_weak_singleton_v1_targets() -> None:
    items, summary = build_title_targets(
        {
            "selected_keywords": [
                {
                    "keyword": "블루투스 키보드",
                    "score": 62.0,
                    "metrics": {"volume": 720.0, "cpc": 115.0},
                }
            ],
            "keyword_clusters": [
                {
                    "cluster_id": "cluster-01",
                    "representative_keyword": "블루투스 키보드",
                    "topic_terms": ["블루투스", "키보드"],
                    "all_keywords": ["블루투스 키보드"],
                }
            ],
            "longtail_suggestions": [
                {
                    "suggestion_id": "longtail-01",
                    "representative_keyword": "블루투스 키보드",
                    "source_keyword": "블루투스 키보드",
                    "longtail_keyword": "블루투스 키보드 실사용 차이",
                    "verification_status": "pending",
                    "projected_score": 66.0,
                },
                {
                    "suggestion_id": "longtail-02",
                    "representative_keyword": "블루투스 키보드",
                    "source_keyword": "블루투스 키보드",
                    "longtail_keyword": "블루투스 키보드 설정 팁",
                    "verification_status": "pending",
                    "projected_score": 65.0,
                },
                {
                    "suggestion_id": "longtail-03",
                    "representative_keyword": "블루투스 키보드",
                    "source_keyword": "블루투스 키보드",
                    "longtail_keyword": "블루투스 키보드 장단점",
                    "verification_status": "pending",
                    "projected_score": 64.0,
                },
            ],
        }
    )

    v1_items = [item for item in items if item["target_mode"] == "longtail_selected"]

    assert summary["mode_counts"]["longtail_selected"] == 1
    assert len(v1_items) == 1
    assert v1_items[0]["base_keyword"] == "블루투스 키보드"


def test_build_title_targets_spreads_v1_across_distinct_families_for_specific_keywords() -> None:
    items, summary = build_title_targets(
        {
            "selected_keywords": [
                {
                    "keyword": "큐센 q104",
                    "score": 58.0,
                    "metrics": {"volume": 240.0, "cpc": 90.0},
                }
            ],
            "keyword_clusters": [
                {
                    "cluster_id": "cluster-01",
                    "representative_keyword": "큐센 q104",
                    "topic_terms": ["큐센", "q104"],
                    "all_keywords": ["큐센 q104"],
                }
            ],
            "longtail_suggestions": [
                {
                    "suggestion_id": "longtail-01",
                    "representative_keyword": "큐센 q104",
                    "source_keyword": "큐센 q104",
                    "longtail_keyword": "큐센 q104 설정 팁",
                    "verification_status": "pending",
                    "projected_score": 71.0,
                },
                {
                    "suggestion_id": "longtail-02",
                    "representative_keyword": "큐센 q104",
                    "source_keyword": "큐센 q104",
                    "longtail_keyword": "큐센 q104 연결 방법",
                    "verification_status": "pending",
                    "projected_score": 70.0,
                },
                {
                    "suggestion_id": "longtail-03",
                    "representative_keyword": "큐센 q104",
                    "source_keyword": "큐센 q104",
                    "longtail_keyword": "큐센 q104 자주 생기는 문제",
                    "verification_status": "pending",
                    "projected_score": 69.0,
                },
            ],
        }
    )

    v1_keywords = {
        item["keyword"]
        for item in items
        if item["target_mode"] == "longtail_selected"
    }

    assert summary["mode_counts"]["longtail_selected"] == 2
    assert "큐센 q104 자주 생기는 문제" in v1_keywords
    assert len(
        {
            keyword
            for keyword in v1_keywords
            if ("설정" in keyword or "연결" in keyword)
        }
    ) == 1


def test_build_title_targets_dedupes_near_duplicate_single_keywords() -> None:
    items, summary = build_title_targets(
        {
            "selected_keywords": [
                {"keyword": "로지텍 지슈스", "score": 48.0},
                {"keyword": "지슈스 마우스", "score": 34.0},
                {"keyword": "로지텍 지슈스 마우스", "score": 22.0},
                {"keyword": "로지텍 지슈스 사전예약", "score": 34.0},
                {"keyword": "로지텍 g304", "score": 39.0},
            ],
            "title_options": {
                "keyword_modes": ["single"],
            },
        }
    )

    single_keywords = {item["keyword"] for item in items if item["target_mode"] == "single"}

    assert summary["mode_counts"]["single"] == 3
    assert single_keywords == {
        "로지텍 지슈스",
        "로지텍 지슈스 사전예약",
        "로지텍 g304",
    }


def test_build_title_targets_uses_deduped_selected_base_for_v1_suggestions() -> None:
    items, summary = build_title_targets(
        {
            "selected_keywords": [
                {"keyword": "로지텍 지슈스", "score": 48.0},
                {"keyword": "지슈스 마우스", "score": 34.0},
                {"keyword": "로지텍 지슈스 마우스", "score": 22.0},
                {"keyword": "로지텍 g304", "score": 39.0},
            ],
            "longtail_suggestions": [
                {
                    "suggestion_id": "longtail-01",
                    "representative_keyword": "로지텍 지슈스",
                    "source_keyword": "로지텍 지슈스",
                    "longtail_keyword": "로지텍 지슈스 설정 팁",
                    "verification_status": "pass",
                    "verified_score": 71.0,
                },
                {
                    "suggestion_id": "longtail-02",
                    "representative_keyword": "지슈스 마우스",
                    "source_keyword": "지슈스 마우스",
                    "longtail_keyword": "지슈스 마우스 설정 팁",
                    "verification_status": "pass",
                    "verified_score": 69.0,
                },
                {
                    "suggestion_id": "longtail-03",
                    "representative_keyword": "로지텍 지슈스 마우스",
                    "source_keyword": "로지텍 지슈스 마우스",
                    "longtail_keyword": "로지텍 지슈스 마우스 설정 팁",
                    "verification_status": "pass",
                    "verified_score": 68.0,
                },
                {
                    "suggestion_id": "longtail-04",
                    "representative_keyword": "로지텍 g304",
                    "source_keyword": "로지텍 g304",
                    "longtail_keyword": "로지텍 g304 실사용 차이",
                    "verification_status": "pass",
                    "verified_score": 72.0,
                },
            ],
            "title_options": {
                "keyword_modes": ["longtail_selected"],
            },
        }
    )

    v1_keywords = {item["keyword"] for item in items if item["target_mode"] == "longtail_selected"}

    assert summary["mode_counts"]["longtail_selected"] == 2
    assert v1_keywords == {
        "로지텍 지슈스 설정 팁",
        "로지텍 g304 실사용 차이",
    }


def test_build_title_targets_caps_seed_anchor_selected_v1_to_one() -> None:
    items, summary = build_title_targets(
        {
            "selected_keywords": [
                {
                    "keyword": "닌텐도 스위치2 사전예약",
                    "score": 32.0,
                    "selection_mode": "seed_anchor",
                    "selection_reason": "seed_intent_preserved",
                }
            ],
            "longtail_suggestions": [
                {
                    "suggestion_id": "longtail-01",
                    "representative_keyword": "닌텐도 스위치2 사전예약",
                    "source_keyword": "닌텐도 스위치2 사전예약",
                    "longtail_keyword": "닌텐도 스위치2 사전예약 전 체크포인트",
                    "verification_status": "pass",
                    "verified_score": 72.0,
                },
                {
                    "suggestion_id": "longtail-02",
                    "representative_keyword": "닌텐도 스위치2 사전예약",
                    "source_keyword": "닌텐도 스위치2 사전예약",
                    "longtail_keyword": "닌텐도 스위치2 사전예약 방법",
                    "verification_status": "pass",
                    "verified_score": 69.0,
                },
            ],
            "title_options": {
                "keyword_modes": ["longtail_selected"],
            },
        }
    )

    assert summary["mode_counts"]["longtail_selected"] == 1
    assert [item["keyword"] for item in items] == ["닌텐도 스위치2 사전예약 전 체크포인트"]
    assert items[0]["source_selection_mode"] == "seed_anchor"
    assert items[0]["source_selection_reason"] == "seed_intent_preserved"


def test_build_title_targets_skips_v1_for_already_concrete_selected_keyword() -> None:
    items, summary = build_title_targets(
        {
            "selected_keywords": [
                {
                    "keyword": "무선 마우스 설정 팁",
                    "score": 18.0,
                    "selection_mode": "fallback",
                    "selection_reason": "top_scored_candidate",
                }
            ],
            "longtail_suggestions": [
                {
                    "suggestion_id": "longtail-01",
                    "representative_keyword": "무선 마우스 설정 팁",
                    "source_keyword": "무선 마우스 설정 팁",
                    "longtail_keyword": "무선 마우스 설정 팁 전 체크포인트",
                    "verification_status": "pending",
                    "projected_score": 52.0,
                }
            ],
            "title_options": {
                "keyword_modes": ["single", "longtail_selected"],
            },
        }
    )

    assert summary["mode_counts"]["single"] == 1
    assert summary["mode_counts"]["longtail_selected"] == 0
    assert [item["keyword"] for item in items] == ["무선 마우스 설정 팁"]


def test_build_title_targets_preserves_selection_metadata_on_single_targets() -> None:
    items, summary = build_title_targets(
        {
            "selected_keywords": [
                {
                    "keyword": "오사카 가성비 호텔",
                    "score": 28.0,
                    "selection_mode": "seed_anchor",
                    "selection_reason": "seed_intent_preserved",
                }
            ],
            "title_options": {
                "keyword_modes": ["single"],
            },
        }
    )

    assert summary["mode_counts"]["single"] == 1
    assert items[0]["keyword"] == "오사카 가성비 호텔"
    assert items[0]["source_selection_mode"] == "seed_anchor"
    assert items[0]["source_selection_reason"] == "seed_intent_preserved"


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


def test_sanitize_related_mode_keyword_collapses_model_noise() -> None:
    assert (
        _sanitize_related_mode_keyword(
            "로지텍 지슈라 스트라이크 m720 실사용 차이",
            representative_keyword="로지텍 지슈라",
        )
        == "로지텍 지슈라 실사용 차이"
    )
    assert (
        _sanitize_related_mode_keyword(
            "로지텍 마우스 맥북 블루투스 연결 문제",
            representative_keyword="로지텍 마우스",
        )
        == "로지텍 마우스 맥북 블루투스 연결 문제"
    )
