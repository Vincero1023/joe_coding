import json
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.analyzer.main import run as analyze_run
from app.expander.main import run as expand_run
from app.main import app


client = TestClient(app)
project_dir = Path(__file__).resolve().parents[1]
expander_sample_dir = project_dir / "app" / "expander" / "sample"


def _fake_autocomplete(query: str) -> list[str]:
    fake_map = {
        "보험": ["보험 추천", "보험 비교"],
        "카드": ["카드 비교", "카드 추천"],
    }
    return fake_map.get(query, [])


def test_expander_accepts_manual_keyword_text() -> None:
    with patch(
        "app.expander.engines.autocomplete_engine.get_naver_autocomplete",
        side_effect=_fake_autocomplete,
    ), patch(
        "app.expander.engines.related_engine.get_naver_related_queries",
        return_value=[],
    ):
        result = expand_run(
            {
                "keywords_text": "보험\n카드",
                "category": "비즈니스경제",
                "analysis_json_path": str(expander_sample_dir / "site_analysis.json"),
            }
        )

    assert result["expanded_keywords"]
    assert any(item["origin"] == "보험" for item in result["expanded_keywords"])
    assert any(item["origin"] == "카드" for item in result["expanded_keywords"])


def test_analyzer_accepts_manual_keyword_text() -> None:
    result = analyze_run({"keywords_text": "보험 추천\n카드 비교"})

    assert len(result["analyzed_keywords"]) == 2
    assert result["analyzed_keywords"][0]["keyword"] in {"보험 추천", "카드 비교"}


def test_expand_endpoint_accepts_manual_keywords() -> None:
    with patch(
        "app.expander.engines.autocomplete_engine.get_naver_autocomplete",
        side_effect=_fake_autocomplete,
    ), patch(
        "app.expander.engines.related_engine.get_naver_related_queries",
        return_value=[],
    ):
        response = client.post(
            "/expand",
            json={
                "input_data": {
                    "keywords_text": "보험\n카드",
                    "category": "비즈니스경제",
                    "analysis_json_path": str(expander_sample_dir / "site_analysis.json"),
                }
            },
        )

    assert response.status_code == 200
    assert response.json()["result"]["expanded_keywords"]


def test_expand_stream_endpoint_emits_progress_and_result() -> None:
    with patch(
        "app.expander.engines.autocomplete_engine.get_naver_autocomplete",
        side_effect=_fake_autocomplete,
    ), patch(
        "app.expander.engines.related_engine.get_naver_related_queries",
        return_value=[],
    ):
        with client.stream(
            "POST",
            "/expand/stream",
            json={
                "input_data": {
                    "keywords_text": "蹂댄뿕\n移대뱶",
                    "category": "鍮꾩쫰?덉뒪寃쎌젣",
                    "analysis_json_path": str(expander_sample_dir / "site_analysis.json"),
                }
            },
        ) as response:
            lines = [line for line in response.iter_lines() if line]

    assert response.status_code == 200
    assert any('"event": "progress"' in line for line in lines)
    assert any('"event": "completed"' in line for line in lines)


def test_expand_analyze_stream_endpoint_emits_analysis_and_result() -> None:
    with patch(
        "app.expander.engines.autocomplete_engine.get_naver_autocomplete",
        side_effect=_fake_autocomplete,
    ), patch(
        "app.expander.engines.related_engine.get_naver_related_queries",
        return_value=[],
    ):
        with client.stream(
            "POST",
            "/expand/analyze/stream",
            json={
                "input_data": {
                    "keywords_text": "보험\n카드",
                    "analysis_json_path": str(expander_sample_dir / "site_analysis.json"),
                    "max_results": 2,
                }
            },
        ) as response:
            lines = [line for line in response.iter_lines() if line]

    assert response.status_code == 200
    assert any('"event": "progress"' in line for line in lines)
    assert any('"event": "analysis"' in line for line in lines)
    assert any('"event": "selection"' in line for line in lines)
    assert any('"event": "completed"' in line for line in lines)
    completed_payload = next(
        json.loads(line)
        for line in lines
        if '"event": "completed"' in line
    )
    assert "selected_keywords" in completed_payload["result"]
    assert "longtail_suggestions" in completed_payload["result"]


def disabled_legacy_generate_title_stream_endpoint_emits_progress_and_result() -> None:
    with client.stream(
        "POST",
        "/generate-title/stream",
        json={
            "input_data": {
                "selected_keywords": [
                    {"keyword": "보험 추천"},
                    {"keyword": "카드 비교"},
                ],
                "title_options": {
                    "mode": "ai",
                },
            }
        },
    ) as response:
        lines = [line for line in response.iter_lines() if line]

    assert response.status_code == 200
    assert any('"event": "progress"' in line for line in lines)
    assert any('"type": "partial_result"' in line for line in lines)
    assert any('"event": "completed"' in line for line in lines)


def test_generate_title_stream_endpoint_emits_progress_and_result() -> None:
    with patch(
        "app.title.title_generator.request_ai_titles",
        side_effect=lambda chunk, options: [
            {
                "keyword": item["keyword"],
                "titles": {
                    "naver_home": [f'{item["keyword"]} 지금 확인', f'{item["keyword"]} 비교 포인트'],
                    "blog": [f'{item["keyword"]} 정리', f'{item["keyword"]} 가이드'],
                    "hybrid": [],
                },
            }
            for item in chunk
        ],
    ):
        with client.stream(
            "POST",
            "/generate-title/stream",
            json={
                "input_data": {
                    "selected_keywords": [
                        {"keyword": "蹂댄뿕 異붿쿇"},
                        {"keyword": "移대뱶 鍮꾧탳"},
                    ],
                    "title_options": {
                        "mode": "ai",
                        "provider": "codex",
                        "model": "gpt-5.4",
                    },
                }
            },
        ) as response:
            lines = [line for line in response.iter_lines() if line]

    assert response.status_code == 200
    assert any('"event": "progress"' in line for line in lines)
    assert any('"event": "completed"' in line for line in lines)


def test_analyze_endpoint_accepts_manual_keywords() -> None:
    response = client.post(
        "/analyze",
        json={"input_data": {"keywords_text": "보험 추천\n카드 비교"}},
    )

    assert response.status_code == 200
    assert len(response.json()["result"]["analyzed_keywords"]) == 2
