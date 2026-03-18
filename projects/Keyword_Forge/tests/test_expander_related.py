from pathlib import Path
from unittest.mock import patch

from app.expander.main import run as expand_run
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
