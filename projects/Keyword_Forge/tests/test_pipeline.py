from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.pipeline.main import run


client = TestClient(app)
project_dir = Path(__file__).resolve().parents[1]
expander_sample_dir = project_dir / "app" / "expander" / "sample"

BUSINESS_CATEGORY = "\ube44\uc988\ub2c8\uc2a4\uacbd\uc81c"
ECONOMY = "\uacbd\uc81c"
ECONOMY_NEWS = "\uacbd\uc81c \ub274\uc2a4"
ECONOMY_POLICY = "\uacbd\uc81c \uc815\ucc45"
STARTUP = "\ucc3d\uc5c5 \uc544\uc774\ud15c"
INSURANCE = "\ubcf4\ud5d8 \ucd94\ucc9c"


def _fake_autocomplete(query: str) -> list[str]:
    fake_map = {
        ECONOMY: [ECONOMY_NEWS, ECONOMY_POLICY, STARTUP],
        ECONOMY_NEWS: [f"{ECONOMY_NEWS} \ucd94\ucc9c", f"{ECONOMY_NEWS} \ube44\uad50"],
        ECONOMY_POLICY: [f"{ECONOMY_POLICY} \ucd94\ucc9c"],
        STARTUP: [f"{STARTUP} \ucd94\ucc9c"],
        INSURANCE: [INSURANCE],
    }
    return fake_map.get(query, [])


def test_generate_title_endpoint_returns_wrapped_title_sets() -> None:
    response = client.post(
        "/generate-title",
        json={
            "input_data": {
                "selected_keywords": [
                    {
                        "keyword": INSURANCE,
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
            }
        },
    )

    assert response.status_code == 200

    result = response.json()["result"]
    assert len(result["generated_titles"]) == 1
    assert len(result["generated_titles"][0]["titles"]["naver_home"]) == 2
    assert len(result["generated_titles"][0]["titles"]["blog"]) == 2


def test_verify_longtail_endpoint_returns_verified_candidates() -> None:
    with patch(
        "app.selector.longtail.analyzer_module.run",
        return_value={
            "analyzed_keywords": [
                {
                    "keyword": "보험 추천 체크리스트",
                    "profitability_grade": "B",
                    "attackability_grade": "1",
                    "combo_grade": "B1",
                    "golden_bucket": "gold",
                    "analysis_mode": "search_metrics",
                    "score": 66.0,
                    "metrics": {
                        "volume": 320.0,
                        "cpc": 180.0,
                        "opportunity": 1.9,
                    },
                }
            ]
        },
    ):
        response = client.post(
            "/verify-longtail",
            json={
                "input_data": {
                    "selected_keywords": [
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
                    ],
                    "longtail_suggestions": [
                        {
                            "suggestion_id": "longtail-01",
                            "cluster_id": "cluster-01",
                            "representative_keyword": "보험 추천",
                            "source_keyword": "보험 추천",
                            "base_phrase": "보험",
                            "modifier_phrase": "추천",
                            "intent_key": "commercial",
                            "intent_label": "비교/추천형",
                            "longtail_keyword": "보험 추천 체크리스트",
                            "projected_profitability_grade": "B",
                            "projected_attackability_grade": "1",
                            "projected_combo_grade": "B1",
                            "projected_golden_bucket": "gold",
                            "projected_score": 70.0,
                            "verification_status": "pending",
                        }
                    ],
                }
            },
        )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["verified_longtail_suggestions"][0]["verification_status"] == "pass"
    assert result["longtail_verification_summary"]["pass_count"] == 1


def test_pipeline_run_returns_all_stage_outputs() -> None:
    with patch("app.collector.service.get_naver_autocomplete", side_effect=_fake_autocomplete), patch(
        "app.expander.engines.autocomplete_engine.get_naver_autocomplete",
        side_effect=_fake_autocomplete,
    ), patch(
        "app.expander.engines.related_engine.get_naver_related_queries",
        return_value=[],
    ):
        result = run(
            {
                "collector": {
                    "mode": "category",
                    "category": BUSINESS_CATEGORY,
                    "category_source": "preset_search",
                    "seed_input": "",
                    "options": {
                        "collect_related": False,
                        "collect_autocomplete": True,
                        "collect_bulk": False,
                    },
                },
                "expander": {
                    "analysis_json_path": str(expander_sample_dir / "site_analysis.json"),
                },
            }
        )

    assert result["collected_keywords"]
    assert result["expanded_keywords"]
    assert result["analyzed_keywords"]
    assert result["selected_keywords"]
    assert result["keyword_clusters"]
    assert isinstance(result["longtail_suggestions"], list)
    assert result["longtail_summary"]["suggestion_count"] == len(result["longtail_suggestions"])
    assert len(result["generated_titles"]) == len(result["selected_keywords"])
    assert all(len(item["titles"]["naver_home"]) == 2 for item in result["generated_titles"][:10])


def test_pipeline_endpoint_runs_end_to_end() -> None:
    with patch("app.collector.service.get_naver_autocomplete", side_effect=_fake_autocomplete), patch(
        "app.expander.engines.autocomplete_engine.get_naver_autocomplete",
        side_effect=_fake_autocomplete,
    ), patch(
        "app.expander.engines.related_engine.get_naver_related_queries",
        return_value=[],
    ):
        response = client.post(
            "/pipeline",
            json={
                "input_data": {
                    "collector": {
                        "mode": "category",
                        "category": BUSINESS_CATEGORY,
                        "category_source": "preset_search",
                        "seed_input": "",
                        "options": {
                            "collect_related": False,
                            "collect_autocomplete": True,
                            "collect_bulk": False,
                        },
                    },
                    "expander": {
                        "analysis_json_path": str(expander_sample_dir / "site_analysis.json"),
                    },
                }
            },
        )

    assert response.status_code == 200

    result = response.json()["result"]
    assert result["selected_keywords"]
    assert result["keyword_clusters"]
    assert isinstance(result["longtail_suggestions"], list)
    assert len(result["generated_titles"]) == len(result["selected_keywords"])


def test_pipeline_passes_title_ai_options_to_title_stage() -> None:
    with patch(
        "app.collector.service.get_naver_autocomplete",
        side_effect=lambda query: [INSURANCE] if query == INSURANCE else [],
    ), patch(
        "app.expander.engines.autocomplete_engine.get_naver_autocomplete",
        side_effect=lambda query: [INSURANCE] if query == INSURANCE else [],
    ), patch(
        "app.expander.engines.related_engine.get_naver_related_queries",
        return_value=[f"{INSURANCE} 비교"],
    ), patch(
        "app.title.title_generator.request_ai_titles",
        return_value=[
            {
                "keyword": INSURANCE,
                "titles": {
                    "naver_home": [
                        "\ubcf4\ud5d8 \ucd94\ucc9c \uc9c0\uae08 \ube44\uad50 \ud3ec\uc778\ud2b8 2\uac00\uc9c0",
                        "\ubcf4\ud5d8 \ucd94\ucc9c \uc120\ud0dd \uae30\uc900 \ub2ec\ub77c\uc84c\ub2e4",
                    ],
                    "blog": [
                        "\ubcf4\ud5d8 \ucd94\ucc9c \uc644\ubcbd \uac00\uc774\ub4dc",
                        "\ubcf4\ud5d8 \ucd94\ucc9c \ube44\uad50 \ud3ec\uc778\ud2b8 \uc815\ub9ac",
                    ],
                },
            }
        ],
    ):
        result = run(
            {
                "collector": {
                    "mode": "seed",
                    "seed_input": INSURANCE,
                    "options": {
                        "collect_related": False,
                        "collect_autocomplete": True,
                        "collect_bulk": False,
                    },
                },
                "expander": {
                    "analysis_json_path": str(expander_sample_dir / "site_analysis.json"),
                },
                "title_options": {
                    "mode": "ai",
                    "provider": "openai",
                    "api_key": "test-key",
                    "model": "gpt-4o-mini",
                },
            }
        )

    assert result["generated_titles"]
    assert result["title_generation_meta"]["used_mode"] in {"ai", "ai_with_template_fallback"}
