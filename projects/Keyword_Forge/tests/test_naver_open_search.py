import io
import json

from app.analyzer.keyword_stats import KeywordStats
from app.analyzer.naver_open_search import (
    NaverOpenSearchClient,
    NaverOpenSearchCredentials,
    build_blog_search_index,
    build_blog_search_requests,
    parse_blog_total_response,
)
from app.expander.utils.tokenizer import normalize_key


class _FakeHttpResponse:
    def __init__(self, payload: dict) -> None:
        self._buffer = io.BytesIO(json.dumps(payload).encode("utf-8"))

    def read(self) -> bytes:
        return self._buffer.read()

    def __enter__(self) -> "_FakeHttpResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_parse_blog_total_response_reads_total() -> None:
    assert parse_blog_total_response({"total": 3042}) == 3042.0


def test_build_blog_search_requests_skips_keywords_with_existing_blog_totals() -> None:
    keyword = "driver insurance compare"
    requests = build_blog_search_requests(
        [
            {"keyword": keyword},
            {"keyword": "tooth insurance compare"},
        ],
        stats_index={
            normalize_key(keyword): KeywordStats(
                keyword=keyword,
                blog_results=3042.0,
                source="naver_blog_search",
            )
        },
    )

    assert requests == ["tooth insurance compare"]


def test_naver_open_search_client_fetches_blog_totals() -> None:
    keyword = "driver insurance compare"
    opener_calls = []

    def fake_opener(request, timeout):
        opener_calls.append(
            {
                "url": request.full_url,
                "timeout": timeout,
            }
        )
        return _FakeHttpResponse({"total": 3042})

    client = NaverOpenSearchClient(
        NaverOpenSearchCredentials(
            client_id="client-id",
            client_secret="client-secret",
        ),
        opener=fake_opener,
    )

    result = client.fetch_blog_totals([keyword])

    assert "/v1/search/blog.json" in opener_calls[0]["url"]
    assert "query=driverinsurancecompare" in opener_calls[0]["url"]
    assert result[normalize_key(keyword)].blog_results == 3042.0


def test_build_blog_search_index_uses_client_and_returns_stats() -> None:
    keyword = "driver insurance compare"

    class _FakeClient:
        def fetch_blog_totals(self, keywords):
            assert keywords == [keyword]
            return {
                normalize_key(keyword): KeywordStats(
                    keyword=keyword,
                    blog_results=3042.0,
                    source="naver_blog_search",
                )
            }

    result = build_blog_search_index(
        {
            "naver_search_api": {
                "client_id": "client-id",
                "client_secret": "client-secret",
            }
        },
        [{"keyword": keyword}],
        client=_FakeClient(),
    )

    assert result[normalize_key(keyword)].blog_results == 3042.0
