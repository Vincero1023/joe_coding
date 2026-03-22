import io
import json

from app.analyzer.keyword_stats import KeywordStats
from app.analyzer.naver_searchad import (
    NaverSearchAdClient,
    NaverSearchAdCredentials,
    SearchAdBidRequest,
    build_searchad_bid_index,
    build_searchad_bid_requests,
    build_searchad_keyword_tool_index,
    build_searchad_keyword_tool_requests,
    generate_signature,
    parse_average_position_bid_response,
    parse_keyword_tool_response,
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


def test_generate_signature_matches_searchad_hmac_contract() -> None:
    signature = generate_signature(
        "1710825600000",
        "POST",
        "/estimate/average-position-bid/keyword",
        "secret-key",
    )

    assert signature == "LQjEDZIpgrcKc1rtOxoHqq2aTI06cyc3IETN2jWG5zc="


def test_credentials_can_load_from_json_file(tmp_path) -> None:
    credential_path = tmp_path / "searchad.credentials.json"
    credential_path.write_text(
        json.dumps(
            {
                "api_key": "file-api-key",
                "secret_key": "file-secret-key",
                "customer_id": "7654321",
            }
        ),
        encoding="utf-8",
    )

    credentials = NaverSearchAdCredentials.from_input(
        {"searchad_credentials_path": str(credential_path)}
    )

    assert credentials == NaverSearchAdCredentials(
        api_key="file-api-key",
        secret_key="file-secret-key",
        customer_id="7654321",
    )


def test_credentials_prefer_local_default_file_over_legacy_root(tmp_path, monkeypatch) -> None:
    local_credential_path = tmp_path / ".local" / "credentials" / "searchad.credentials.json"
    local_credential_path.parent.mkdir(parents=True)
    local_credential_path.write_text(
        json.dumps(
            {
                "api_key": "local-api-key",
                "secret_key": "local-secret-key",
                "customer_id": "1234567",
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "searchad.credentials.json").write_text(
        json.dumps(
            {
                "api_key": "legacy-api-key",
                "secret_key": "legacy-secret-key",
                "customer_id": "7654321",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    credentials = NaverSearchAdCredentials.from_input({})

    assert credentials == NaverSearchAdCredentials(
        api_key="local-api-key",
        secret_key="local-secret-key",
        customer_id="1234567",
    )


def test_credentials_fall_back_to_legacy_root_file_when_local_default_is_missing(tmp_path, monkeypatch) -> None:
    (tmp_path / "searchad.credentials.json").write_text(
        json.dumps(
            {
                "api_key": "legacy-api-key",
                "secret_key": "legacy-secret-key",
                "customer_id": "7654321",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    credentials = NaverSearchAdCredentials.from_input({})

    assert credentials == NaverSearchAdCredentials(
        api_key="legacy-api-key",
        secret_key="legacy-secret-key",
        customer_id="7654321",
    )


def test_parse_average_position_bid_response_maps_pc_top_positions() -> None:
    keyword = "driver insurance compare"
    parsed = parse_average_position_bid_response(
        {
            "device": "PC",
            "estimate": [
                {"keyword": keyword, "position": 1, "bid": 1570},
                {"keyword": keyword, "position": 2, "bid": 1560},
                {"keyword": keyword, "position": 3, "bid": 1470},
            ],
        }
    )

    item = parsed[normalize_key(keyword)]
    assert item.source == "naver_searchad"
    assert item.bid_1 == 1570.0
    assert item.bid_2 == 1560.0
    assert item.bid_3 == 1470.0


def test_parse_average_position_bid_response_maps_mobile_positions() -> None:
    keyword = "driver insurance compare"
    parsed = parse_average_position_bid_response(
        {
            "device": "MOBILE",
            "estimate": [
                {"keyword": keyword, "position": 1, "bid": 990},
                {"keyword": keyword, "position": 2, "bid": 880},
                {"keyword": keyword, "position": 3, "bid": 770},
            ],
        },
        device="MOBILE",
    )

    item = parsed[normalize_key(keyword)]
    assert item.mobile_bid_1 == 990.0
    assert item.mobile_bid_2 == 880.0
    assert item.mobile_bid_3 == 770.0


def test_parse_keyword_tool_response_maps_request_order() -> None:
    keyword = "driver insurance compare"
    parsed = parse_keyword_tool_response(
        {
            "keywordList": [
                {
                    "relKeyword": "???? ?? ?????",
                    "monthlyPcQcCnt": "< 10",
                    "monthlyMobileQcCnt": "140",
                    "monthlyAvePcClkCnt": 0.3,
                    "monthlyAveMobileClkCnt": 2.5,
                }
            ]
        },
        request_keywords=[keyword],
    )

    item = parsed[normalize_key(keyword)]
    assert item.keyword == keyword
    assert item.pc_searches == 10.0
    assert item.mobile_searches == 140.0
    assert item.mobile_clicks == 2.5


def test_parse_average_position_bid_response_falls_back_to_request_keywords() -> None:
    keyword = "driver insurance compare"
    parsed = parse_average_position_bid_response(
        {
            "device": "PC",
            "estimate": [
                {"keyword": "???? ?? ?????", "position": 1, "bid": 1570},
                {"keyword": "???? ?? ?????", "position": 2, "bid": 1560},
                {"keyword": "???? ?? ?????", "position": 3, "bid": 1470},
            ],
        },
        request_items=[
            {"key": keyword, "position": 1},
            {"key": keyword, "position": 2},
            {"key": keyword, "position": 3},
        ],
    )

    item = parsed[normalize_key(keyword)]
    assert item.keyword == keyword
    assert item.bid_3 == 1470.0


def test_build_searchad_bid_requests_skips_keywords_with_existing_bids() -> None:
    keyword = "driver insurance compare"
    requests = build_searchad_bid_requests(
        [
            {"keyword": keyword},
            {"keyword": "tooth insurance compare"},
        ],
        stats_index={
            normalize_key(keyword): KeywordStats(
                keyword=keyword,
                bid_1=500.0,
                bid_2=300.0,
                bid_3=200.0,
                source="text_line",
            )
        },
    )

    assert requests == [
        SearchAdBidRequest(keyword=keyword, positions=(4, 5, 6, 7, 8, 9, 10), device="PC"),
        SearchAdBidRequest(keyword=keyword, positions=(1, 2, 3, 4, 5), device="MOBILE"),
        SearchAdBidRequest(keyword="tooth insurance compare", positions=(1, 2, 3, 4, 5, 6, 7, 8, 9, 10), device="PC"),
        SearchAdBidRequest(keyword="tooth insurance compare", positions=(1, 2, 3, 4, 5), device="MOBILE"),
    ]


def test_build_searchad_keyword_tool_requests_skips_keywords_with_existing_metrics() -> None:
    keyword = "driver insurance compare"
    requests = build_searchad_keyword_tool_requests(
        [
            {"keyword": keyword},
            {"keyword": "tooth insurance compare"},
        ],
        stats_index={
            normalize_key(keyword): KeywordStats(
                keyword=keyword,
                pc_searches=50.0,
                mobile_searches=150.0,
                pc_clicks=1.2,
                mobile_clicks=4.8,
                source="naver_searchad_keywordtool",
            )
        },
    )

    assert requests == ["tooth insurance compare"]


def test_searchad_client_fetches_and_maps_bid_stats() -> None:
    keyword = "driver insurance compare"
    opener_calls = []

    def fake_opener(request, timeout):
        opener_calls.append(
            {
                "url": request.full_url,
                "body": json.loads(request.data.decode("utf-8")),
                "timeout": timeout,
            }
        )
        return _FakeHttpResponse(
            {
                "device": "PC",
                "estimate": [
                    {"keyword": keyword, "position": 1, "bid": 1570},
                    {"keyword": keyword, "position": 2, "bid": 1560},
                    {"keyword": keyword, "position": 3, "bid": 1470},
                ],
            }
        )

    client = NaverSearchAdClient(
        NaverSearchAdCredentials(
            api_key="api-key",
            secret_key="secret-key",
            customer_id="1234567",
        ),
        opener=fake_opener,
    )

    result = client.fetch_average_position_bid_stats(
        [SearchAdBidRequest(keyword=keyword, positions=(1, 2, 3))]
    )

    assert opener_calls[0]["url"].endswith("/estimate/average-position-bid/keyword")
    assert opener_calls[0]["body"]["device"] == "PC"
    assert opener_calls[0]["body"]["items"] == [
        {"key": "driverinsurancecompare", "position": 1},
        {"key": "driverinsurancecompare", "position": 2},
        {"key": "driverinsurancecompare", "position": 3},
    ]
    assert result[normalize_key(keyword)].bid_1 == 1570.0


def test_build_searchad_bid_index_uses_client_and_returns_stats() -> None:
    keyword = "driver insurance compare"

    class _FakeClient:
        def fetch_average_position_bid_stats(self, requests, *, keyword_batch_size):
            assert keyword_batch_size == 50
            assert requests == [
                SearchAdBidRequest(keyword=keyword, positions=(1, 2, 3, 4, 5, 6, 7, 8, 9, 10), device="PC"),
                SearchAdBidRequest(keyword=keyword, positions=(1, 2, 3, 4, 5), device="MOBILE"),
            ]
            return {
                normalize_key(keyword): KeywordStats(
                    keyword=keyword,
                    bid_1=1570.0,
                    bid_2=1560.0,
                    bid_3=1470.0,
                    source="naver_searchad",
                )
            }

    result = build_searchad_bid_index(
        {
            "searchad": {
                "api_key": "api-key",
                "secret_key": "secret-key",
                "customer_id": "1234567",
            }
        },
        [{"keyword": keyword}],
        client=_FakeClient(),
    )

    assert result[normalize_key(keyword)].bid_2 == 1560.0


def test_build_searchad_keyword_tool_index_uses_client_and_returns_stats() -> None:
    keyword = "driver insurance compare"

    class _FakeClient:
        def fetch_keyword_tool_stats(self, keywords, *, keyword_batch_size):
            assert keyword_batch_size == 1
            assert keywords == [keyword]
            return {
                normalize_key(keyword): KeywordStats(
                    keyword=keyword,
                    pc_searches=90.0,
                    mobile_searches=410.0,
                    pc_clicks=3.4,
                    mobile_clicks=22.1,
                    source="naver_searchad_keywordtool",
                )
            }

    result = build_searchad_keyword_tool_index(
        {
            "searchad": {
                "api_key": "api-key",
                "secret_key": "secret-key",
                "customer_id": "1234567",
            }
        },
        [{"keyword": keyword}],
        client=_FakeClient(),
    )

    assert result[normalize_key(keyword)].mobile_searches == 410.0
