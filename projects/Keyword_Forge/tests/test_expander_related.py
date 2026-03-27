from pathlib import Path
from threading import Event
from unittest.mock import patch

from app.expander.main import run as expand_run
from app.expander.main import run_with_analysis_progress
from app.expander.main import run_with_progress
from app.expander.sources.naver_related import (
    _extract_qra_api_url,
    _extract_related_queries,
    _extract_related_queries_from_qra_response,
)
from app.expander.utils.filtering import filter_expansions


project_dir = Path(__file__).resolve().parents[1]
expander_sample_dir = project_dir / "app" / "expander" / "sample"


def test_extract_qra_api_url_from_search_html() -> None:
    html = """
    <script>
    naver.search.fender["prs_template_qra_desk.ts"] = function() {
        return {
            body: {
                props: {
                    apiURL: "https://s.search.naver.com/p/qra/1/search.naver?api_type=nd&query=butter-rice-cake&ssc=tab.nx.all"
                }
            }
        };
    };
    </script>
    """

    result = _extract_qra_api_url(html)

    assert result == "https://s.search.naver.com/p/qra/1/search.naver?api_type=nd&query=butter-rice-cake&ssc=tab.nx.all"


def test_extract_related_queries_from_qra_response() -> None:
    response_body = """
    {
      "result": {
        "contents": [
          {"query": "butter rice cake calories"},
          {"query": "butter rice cake recipe"},
          {"query": "butter rice cake"},
          {"query": "seoul butter rice cake"}
        ]
      }
    }
    """

    result = _extract_related_queries_from_qra_response(response_body, "butter rice cake")

    assert result == [
        "butter rice cake calories",
        "butter rice cake recipe",
        "seoul butter rice cake",
    ]


def test_extract_related_queries_from_legacy_section() -> None:
    html = """
    <section class="sc_new sp_related" id="nx_right_related_keywords">
        <div class="api_subject_bx _related_box">
            <div class="related_srch">
                <ul class="lst_related_srch _list_box">
                    <li class="item">
                        <a class="keyword" href="?query=tesla+stock">
                            <div class="tit">tesla stock</div>
                        </a>
                    </li>
                    <li class="item">
                        <a class="keyword" href="?query=tesla+price">
                            <div class="tit">tesla price</div>
                        </a>
                    </li>
                    <li class="item">
                        <a class="keyword" href="?query=tesla">
                            <div class="tit">tesla</div>
                        </a>
                    </li>
                </ul>
            </div>
        </div>
    </section>
    """

    result = _extract_related_queries(html, "tesla")

    assert result == ["tesla stock", "tesla price"]


def test_filter_expansions_keeps_single_token_related_keywords() -> None:
    result = filter_expansions(
        [
            {
                "keyword": "tesla",
                "origin": "electric car",
                "type": "related",
            }
        ]
    )

    assert result == [
        {
            "keyword": "tesla",
            "origin": "electric car",
            "type": "related",
        }
    ]


def test_expander_defaults_to_real_related_and_skips_combinator() -> None:
    with patch(
        "app.expander.engines.autocomplete_engine.get_naver_autocomplete",
        return_value=[],
    ), patch(
        "app.expander.engines.related_engine.get_naver_related_queries",
        return_value=["insurance comparison", "auto insurance recommendation"],
    ):
        result = expand_run(
            {
                "keywords_text": "insurance",
                "analysis_json_path": str(expander_sample_dir / "site_analysis.json"),
            }
        )

    assert result["expanded_keywords"] == [
        {"keyword": "insurance comparison", "origin": "insurance", "type": "related"},
        {"keyword": "auto insurance recommendation", "origin": "insurance", "type": "related"},
    ]


def test_expander_can_disable_seed_filter_and_limit_result_count() -> None:
    with patch(
        "app.expander.engines.autocomplete_engine.get_naver_autocomplete",
        return_value=["insurance premium", "insurance deductible"],
    ), patch(
        "app.expander.engines.related_engine.get_naver_related_queries",
        return_value=["coverage options", "policy rider"],
    ):
        result = expand_run(
            {
                "keywords_text": "insurance",
                "analysis_json_path": str(expander_sample_dir / "site_analysis.json"),
                "enable_seed_filter": False,
                "max_results": 2,
            }
        )

    assert result["expanded_keywords"] == [
        {"keyword": "insurance premium", "origin": "insurance", "type": "autocomplete"},
        {"keyword": "insurance deductible", "origin": "insurance", "type": "autocomplete"},
    ]


def test_expander_stop_event_returns_partial_results() -> None:
    stop_event = Event()
    progress_types: list[str] = []

    def on_progress(payload: dict[str, object]) -> None:
        progress_type = str(payload.get("type") or "")
        if progress_type:
            progress_types.append(progress_type)
        if progress_type == "keyword_results":
            stop_event.set()

    with patch(
        "app.expander.engines.autocomplete_engine.get_naver_autocomplete",
        return_value=["insurance premium", "insurance deductible"],
    ), patch(
        "app.expander.engines.related_engine.get_naver_related_queries",
        return_value=["insurance comparison"],
    ):
        result = run_with_progress(
            {
                "keywords_text": "insurance",
                "analysis_json_path": str(expander_sample_dir / "site_analysis.json"),
                "enable_seed_filter": False,
            },
            progress_callback=on_progress,
            stop_event=stop_event,
        )

    assert result["stopped"] is True
    assert result["expanded_keywords"]
    assert "keyword_results" in progress_types


def test_run_with_analysis_progress_emits_incremental_selection_snapshots() -> None:
    analysis_events: list[dict[str, object]] = []
    selection_events: list[dict[str, object]] = []

    def fake_autocomplete(query: str) -> list[str]:
        fake_map = {
            "보험": ["보험 추천"],
            "카드": ["카드 추천"],
        }
        return fake_map.get(query, [])

    def fake_analyzer(input_data: dict[str, object]) -> dict[str, object]:
        items = [
            item
            for item in input_data.get("expanded_keywords", [])
            if isinstance(item, dict)
        ]
        analyzed = [
            {
                "keyword": str(item.get("keyword") or "").strip(),
                "profitability_grade": "A",
                "attackability_grade": "2",
                "combo_grade": "A2",
                "golden_bucket": "gold",
                "score": 74.0,
                "metrics": {"volume": 320.0, "cpc": 180.0},
            }
            for item in items
            if str(item.get("keyword") or "").strip()
        ]
        return {
            "analyzed_keywords": analyzed,
            "debug": {
                "api_usage": {"summary": {"total_calls": 0}, "services": []},
            },
        }

    def fake_selector(input_data: dict[str, object]) -> dict[str, object]:
        items = [
            item
            for item in input_data.get("analyzed_keywords", [])
            if isinstance(item, dict)
        ]
        return {
            "selected_keywords": items,
            "keyword_clusters": [],
            "content_map_summary": {
                "keyword_count": len(items),
                "cluster_count": 0,
                "article_count": 0,
                "split_cluster_count": 0,
            },
            "longtail_suggestions": [
                {
                    "suggestion_id": f"longtail-{index + 1:02d}",
                    "longtail_keyword": f"{item['keyword']} 가이드",
                }
                for index, item in enumerate(items)
            ],
            "longtail_summary": {
                "suggestion_count": len(items),
            },
            "longtail_options": {
                "optional_suffix_keys": ["guide"],
            },
            "cannibalization_report": {
                "summary": {"issue_group_count": 0},
            },
            "debug": {
                "api_usage": {"summary": {"total_calls": 0}, "services": []},
                "selection_summary": {
                    "input_keyword_count": len(items),
                    "selected_keyword_count": len(items),
                },
            },
        }

    with patch(
        "app.expander.engines.autocomplete_engine.get_naver_autocomplete",
        side_effect=fake_autocomplete,
    ), patch(
        "app.expander.engines.related_engine.get_naver_related_queries",
        return_value=[],
    ), patch(
        "app.expander.main.analyzer_module.run",
        side_effect=fake_analyzer,
    ), patch(
        "app.expander.main.selector_module.run",
        side_effect=fake_selector,
    ):
        result = run_with_analysis_progress(
            {
                "keywords_text": "보험\n카드",
                "analysis_json_path": str(expander_sample_dir / "site_analysis.json"),
                "enable_seed_filter": False,
            },
            analysis_callback=analysis_events.append,
            selection_callback=selection_events.append,
        )

    assert [event["type"] for event in analysis_events] == [
        "analysis_started",
        "analysis_progress",
        "analysis_progress",
        "analysis_completed",
    ]
    assert [event["total_selected"] for event in selection_events] == [1, 2]
    assert [item["keyword"] for item in result["analyzed_keywords"]] == [
        "보험 추천",
        "카드 추천",
    ]
    assert [item["keyword"] for item in result["selected_keywords"]] == [
        "보험 추천",
        "카드 추천",
    ]
    assert result["longtail_summary"]["suggestion_count"] == 2
    assert result["debug"]["analysis_summary"]["analysis_batch_count"] == 2
