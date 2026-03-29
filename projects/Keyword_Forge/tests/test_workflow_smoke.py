import json
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)
project_dir = Path(__file__).resolve().parents[1]
expander_sample_dir = project_dir / "app" / "expander" / "sample"


def _fake_autocomplete(query: str) -> list[str]:
    fake_map = {
        "경제": ["경제 뉴스", "경제 정책", "창업 아이템"],
        "경제 뉴스": ["경제 뉴스 추천", "경제 뉴스 비교"],
        "경제 정책": ["경제 정책 추천"],
        "창업 아이템": ["창업 아이템 추천"],
    }
    return fake_map.get(query, [])


def test_keyword_discovery_to_selection_stream_smoke() -> None:
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
                    "keywords_text": "경제",
                    "analysis_json_path": str(expander_sample_dir / "site_analysis.json"),
                    "max_results": 2,
                    "select_options": {
                        "mode": "combo_filter",
                        "allowed_profitability_grades": ["A", "B", "C", "D", "E", "F"],
                        "allowed_attackability_grades": ["1", "2", "3", "4", "5", "6"],
                    },
                }
            },
        ) as response:
            lines = [line for line in response.iter_lines() if line]

    assert response.status_code == 200
    assert any('"event": "analysis"' in line for line in lines)
    assert any('"event": "selection"' in line for line in lines)
    completed_payload = next(
        json.loads(line)
        for line in lines
        if '"event": "completed"' in line
    )
    result = completed_payload["result"]
    assert result["expanded_keywords"]
    assert result["analyzed_keywords"]
    assert "selection_profile" in result
    assert "rejection_summary" in result["selection_profile"]


def test_manual_analyze_to_selection_smoke() -> None:
    analyze_response = client.post(
        "/analyze",
        json={"input_data": {"keywords_text": "보험 추천\n보험 비교\n보험 가이드"}},
    )

    assert analyze_response.status_code == 200
    analyzed_keywords = analyze_response.json()["result"]["analyzed_keywords"]
    assert analyzed_keywords

    select_response = client.post(
        "/select",
        json={
            "input_data": {
                "analyzed_keywords": analyzed_keywords,
                "select_options": {
                    "mode": "combo_filter",
                    "allowed_profitability_grades": ["A", "B", "C", "D", "E", "F"],
                    "allowed_attackability_grades": ["1", "2", "3", "4", "5", "6"],
                },
            }
        },
    )

    assert select_response.status_code == 200
    result = select_response.json()["result"]
    assert "selected_keywords" in result
    assert "selection_profile" in result
    assert "rejection_summary" in result["selection_profile"]


def test_selection_to_title_smoke() -> None:
    analyzed_keywords = [
        {
            "keyword": "보험 추천",
            "profitability_grade": "A",
            "attackability_grade": "2",
            "combo_grade": "A2",
            "golden_bucket": "gold",
            "score": 76.0,
            "metrics": {
                "volume": 1200.0,
                "cpc": 210.0,
                "competition": 0.42,
                "bid": 160.0,
                "total_clicks": 84.0,
            },
        }
    ]

    select_response = client.post(
        "/select",
        json={
            "input_data": {
                "analyzed_keywords": analyzed_keywords,
                "select_options": {
                    "mode": "combo_filter",
                    "allowed_profitability_grades": ["A", "B", "C"],
                    "allowed_attackability_grades": ["1", "2", "3"],
                },
            }
        },
    )

    assert select_response.status_code == 200
    selected_keywords = select_response.json()["result"]["selected_keywords"]
    assert len(selected_keywords) == 1

    title_response = client.post(
        "/generate-title",
        json={
            "input_data": {
                "selected_keywords": selected_keywords,
                "title_options": {
                    "mode": "template",
                    "keyword_modes": ["single"],
                    "surface_modes": ["naver_home", "blog"],
                    "surface_counts": {
                        "naver_home": 1,
                        "blog": 1,
                        "hybrid": 0,
                    },
                },
            }
        },
    )

    assert title_response.status_code == 200
    result = title_response.json()["result"]
    assert len(result["generated_titles"]) == 1
    assert len(result["generated_titles"][0]["titles"]["naver_home"]) == 1
    assert len(result["generated_titles"][0]["titles"]["blog"]) == 1
