from __future__ import annotations

import json

from app.collector.naver_trend import NaverTrendClient
from app.collector.service import CollectorService
from app.expander.sources.naver_related import _fetch_qra_related_queries
from app.expander.utils.throttle import get_naver_request_gap_seconds


class _DummyResponse:
    def __init__(self, body: str) -> None:
        self._body = body.encode("utf-8")

    def __enter__(self) -> "_DummyResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def read(self) -> bytes:
        return self._body


def test_get_naver_request_gap_seconds_defaults_to_slow_mode(monkeypatch) -> None:
    monkeypatch.delenv("KEYWORD_FORGE_NAVER_REQUEST_GAP_SECONDS", raising=False)

    assert get_naver_request_gap_seconds() == 2.0


def test_collector_search_fallback_waits_for_naver_throttle(monkeypatch) -> None:
    waits: list[str] = []

    monkeypatch.setattr(
        "app.collector.service.wait_for_naver_keyword_request",
        lambda: waits.append("wait"),
    )
    monkeypatch.setattr(
        "app.collector.service.urlopen",
        lambda request, timeout=0: _DummyResponse("<html><body></body></html>"),
    )

    service = CollectorService()

    assert service._search_naver_results("보험", "nexearch") == []
    assert waits == ["wait"]


def test_naver_trend_fetch_json_waits_for_naver_throttle(monkeypatch) -> None:
    waits: list[str] = []

    monkeypatch.setattr(
        "app.collector.naver_trend.wait_for_naver_keyword_request",
        lambda: waits.append("wait"),
    )
    monkeypatch.setattr(
        "app.collector.naver_trend.urlopen",
        lambda request, timeout=0: _DummyResponse('{"categoryTree": []}'),
    )

    client = NaverTrendClient()

    assert client._fetch_json(
        "/accounts/preferred-category/naver_blog",
        {"contentType": "text"},
        "NID_AUT=1",
    ) == {"categoryTree": []}
    assert waits == ["wait"]


def test_qra_related_query_fetch_waits_for_naver_throttle(monkeypatch) -> None:
    waits: list[str] = []
    html = """
    <script>
    apiURL: "https://s.search.naver.com/p/qra/1/search.naver?api_type=nd&query=test"
    </script>
    """
    body = json.dumps(
        {
            "result": {
                "contents": [
                    {"query": "테스트 추천"},
                ]
            }
        }
    )

    monkeypatch.setattr(
        "app.expander.sources.naver_related.wait_for_naver_keyword_request",
        lambda: waits.append("wait"),
    )
    monkeypatch.setattr(
        "app.expander.sources.naver_related.urlopen",
        lambda request, timeout=0: _DummyResponse(body),
    )

    assert _fetch_qra_related_queries(
        html=html,
        keyword="테스트",
        referer_url="https://search.naver.com/search.naver?query=%ED%85%8C%EC%8A%A4%ED%8A%B8",
    ) == ["테스트 추천"]
    assert waits == ["wait"]
