from app.analyzer.keyword_stats import KeywordStats
from app.analyzer.keywordmaster_benchmark import (
    build_keywordmaster_benchmark_index,
    build_keywordmaster_benchmark_requests,
    parse_keywordmaster_keyword_response,
)
from app.expander.utils.tokenizer import normalize_key


def test_parse_keywordmaster_keyword_response_maps_all_primary_metrics() -> None:
    keyword = "테슬라 모델y 가격"
    result = parse_keywordmaster_keyword_response(
        {
            "main": {
                "keyword": "테슬라모델Y가격",
                "pcSearch": 600,
                "moSearch": 2460,
                "pcClick": 1.4,
                "moClick": 42.6,
                "blogPosts": 80916,
                "pcBids": [5460, 1380, 1000, 730, 610, 550, 510, 70, 70, 70],
                "moBids": [4550, 1200, 830, 670, 500],
            }
        },
        request_keyword=keyword,
    )

    assert result is not None
    assert result.keyword == keyword
    assert result.pc_searches == 600.0
    assert result.mobile_searches == 2460.0
    assert result.blog_results == 80916.0
    assert result.pc_clicks == 1.4
    assert result.mobile_clicks == 42.6
    assert result.bid_1 == 5460.0
    assert result.bid_2 == 1380.0
    assert result.bid_3 == 1000.0
    assert result.mobile_bid_1 == 4550.0
    assert result.resolved_average_bid() == 2613.3333


def test_build_keywordmaster_benchmark_requests_only_targets_missing_or_flat_stats() -> None:
    fully_measured = "테슬라 모델y 가격"
    flat_bid_keyword = "테슬라코리아클럽"
    missing_keyword = "새 키워드"

    requests = build_keywordmaster_benchmark_requests(
        [
            {"keyword": fully_measured},
            {"keyword": flat_bid_keyword},
            {"keyword": missing_keyword},
        ],
        stats_index={
            normalize_key(fully_measured): KeywordStats(
                keyword=fully_measured,
                pc_searches=600.0,
                mobile_searches=2460.0,
                blog_results=80916.0,
                bid_1=5460.0,
                bid_2=1380.0,
                bid_3=1000.0,
                source="manual",
            ),
            normalize_key(flat_bid_keyword): KeywordStats(
                keyword=flat_bid_keyword,
                pc_searches=240.0,
                mobile_searches=1060.0,
                bid_1=70.0,
                bid_2=70.0,
                bid_3=70.0,
                source="naver_searchad",
            ),
        },
    )

    assert requests == [flat_bid_keyword, missing_keyword]


def test_build_keywordmaster_benchmark_index_uses_client() -> None:
    keyword = "테슬라코리아클럽"

    class _FakeClient:
        def fetch_keyword_stats(self, keywords, *, max_workers):
            assert keywords == [keyword]
            assert max_workers == 4
            return {
                normalize_key(keyword): KeywordStats(
                    keyword=keyword,
                    pc_searches=240.0,
                    mobile_searches=1060.0,
                    blog_results=4731.0,
                    bid_1=70.0,
                    bid_2=70.0,
                    bid_3=70.0,
                    source="keywordmaster_benchmark",
                )
            }

    result = build_keywordmaster_benchmark_index(
        {
            "keywordmaster_benchmark": {
                "enabled": True,
                "max_workers": 4,
            }
        },
        [{"keyword": keyword}],
        client=_FakeClient(),
    )

    assert result[normalize_key(keyword)].blog_results == 4731.0
