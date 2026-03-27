import json
from io import BytesIO
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError

import pytest

from app.collector.categories import CATEGORY_CHOICES, resolve_category_name
from app.collector.naver_trend import (
    NaverTrendAuthError,
    NaverTrendClient,
    NaverTrendOptions,
    resolve_trend_date,
)


def test_naver_trend_cache_file_is_project_root_relative() -> None:
    from app.collector import naver_trend

    expected = Path(naver_trend.__file__).resolve().parents[2] / ".local" / "naver_playwright" / "naver_creator_session.json"

    assert naver_trend._LOCAL_SESSION_CACHE_FILE == expected


def test_naver_trend_client_retries_with_cached_local_session(
    monkeypatch,
    tmp_path,
) -> None:
    cache_file = tmp_path / "naver_creator_session.json"
    cache_file.write_text(
        json.dumps({"cookie_header": "cached_cookie=1"}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr("app.collector.naver_trend._LOCAL_SESSION_CACHE_FILE", cache_file)

    calls: list[tuple[str, str]] = []

    def fake_fetcher(endpoint: str, params: dict[str, str], auth_cookie: str):
        calls.append((endpoint, auth_cookie))
        if auth_cookie == "stale_cookie=1":
            raise NaverTrendAuthError("Forbidden")
        if endpoint.startswith("/accounts/preferred-category/"):
            return {
                "categoryTree": [
                    {
                        "categories": [
                            {"id": "국내여행", "name": "국내여행"},
                        ]
                    }
                ]
            }
        return {
            "data": [
                {
                    "category": "국내여행",
                    "queryList": [
                        {"query": "벚꽃여행", "rank": 1, "rankChange": "new"},
                    ],
                }
            ]
        }

    client = NaverTrendClient(json_fetcher=fake_fetcher)
    result = client.collect_category_keywords(
        topic_name="국내여행",
        options=NaverTrendOptions(
            service="naver_blog",
            auth_cookie="stale_cookie=1",
            fallback_to_preset_search=False,
        ),
    )

    assert result.topic_id == "국내여행"
    assert [item.query for item in result.keywords] == ["벚꽃여행"]
    assert calls == [
        ("/accounts/preferred-category/naver_blog", "stale_cookie=1"),
        ("/accounts/preferred-category/naver_blog", "cached_cookie=1"),
        ("/trend/category", "cached_cookie=1"),
    ]


def test_category_choices_match_current_naver_trend_snapshot() -> None:
    assert CATEGORY_CHOICES == (
        "문학·책",
        "영화",
        "미술·디자인",
        "공연·전시",
        "음악",
        "드라마",
        "스타·연예인",
        "만화·애니",
        "방송",
        "일상·생각",
        "육아·결혼",
        "반려동물",
        "좋은글·이미지",
        "패션·미용",
        "인테리어·DIY",
        "요리·레시피",
        "상품리뷰",
        "원예·재배",
        "게임",
        "스포츠",
        "사진",
        "자동차",
        "취미",
        "국내여행",
        "세계여행",
        "맛집",
        "IT·컴퓨터",
        "사회·정치",
        "건강·의학",
        "비즈니스·경제",
        "어학·외국어",
        "교육·학문",
    )
    assert resolve_category_name("해외여행") == "세계여행"
    assert resolve_category_name("비즈니스경제") == "비즈니스·경제"


def test_naver_trend_client_uses_recent_non_empty_date_when_requested_date_is_empty() -> None:
    calls: list[tuple[str, str]] = []

    def fake_fetcher(endpoint: str, params: dict[str, str], auth_cookie: str):
        if endpoint.startswith("/accounts/preferred-category/"):
            return {
                "categoryTree": [
                    {
                        "categories": [
                            {"id": "비즈니스·경제", "name": "비즈니스·경제"},
                        ]
                    }
                ]
            }

        requested_date = str(params.get("date"))
        calls.append((endpoint, requested_date))
        if requested_date == "2026-03-18":
            return {"data": [{"category": "비즈니스·경제", "queryList": []}]}
        return {
            "data": [
                {
                    "category": "비즈니스·경제",
                    "queryList": [
                        {"query": "청년미래적금", "rank": 1, "rankChange": 2},
                    ],
                }
            ]
        }

    client = NaverTrendClient(json_fetcher=fake_fetcher)
    result = client.collect_category_keywords(
        topic_name="비즈니스·경제",
        options=NaverTrendOptions(
            service="naver_blog",
            auth_cookie="cookie=value",
            date="2026-03-18",
            fallback_to_preset_search=False,
        ),
    )

    assert result.date == "2026-03-17"
    assert [item.query for item in result.keywords] == ["청년미래적금"]
    assert calls == [
        ("/trend/category", "2026-03-18"),
        ("/trend/category", "2026-03-17"),
    ]


def test_resolve_trend_date_defaults_to_current_kst_day_when_blank(monkeypatch) -> None:
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 3, 21, 9, 15, 0, tzinfo=tz)

    monkeypatch.setattr("app.collector.naver_trend.datetime", FixedDateTime)

    assert resolve_trend_date("") == "2026-03-21"


def test_naver_trend_client_validate_session_accepts_inline_cookie(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr("app.collector.naver_trend._LOCAL_SESSION_CACHE_FILE", tmp_path / "missing.json")
    calls: list[tuple[str, str]] = []

    def fake_fetcher(endpoint: str, params: dict[str, str], auth_cookie: str):
        calls.append((endpoint, auth_cookie))
        return {
            "categoryTree": [
                {
                    "categories": [
                        {"id": "domestic-travel", "name": "국내여행"},
                        {"id": "restaurants", "name": "맛집"},
                    ]
                },
                {
                    "categories": [
                        {"id": "pets", "name": "반려동물"},
                    ]
                },
            ]
        }

    client = NaverTrendClient(json_fetcher=fake_fetcher)
    result = client.validate_session(
        options=NaverTrendOptions(
            service="naver_blog",
            content_type="text",
            auth_cookie="NID_AUT=test; NID_SES=session",
        )
    )

    assert result["valid"] is True
    assert result["status"] == "authenticated"
    assert result["auth_source"] == "inline"
    assert result["checked_sources"] == ["inline"]
    assert result["topic_group_count"] == 2
    assert result["topic_count"] == 3
    assert calls == [
        ("/accounts/preferred-category/naver_blog", "NID_AUT=test; NID_SES=session"),
    ]


def test_naver_trend_client_validate_session_retries_with_cached_session(
    monkeypatch,
    tmp_path,
) -> None:
    cache_file = tmp_path / "naver_creator_session.json"
    cache_file.write_text(
        json.dumps({"cookie_header": "cached_cookie=1"}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr("app.collector.naver_trend._LOCAL_SESSION_CACHE_FILE", cache_file)

    calls: list[tuple[str, str]] = []

    def fake_fetcher(endpoint: str, params: dict[str, str], auth_cookie: str):
        calls.append((endpoint, auth_cookie))
        if auth_cookie == "stale_cookie=1":
            raise NaverTrendAuthError("Forbidden")
        return {
            "categoryTree": [
                {
                    "categories": [
                        {"id": "domestic-travel", "name": "국내여행"},
                    ]
                }
            ]
        }

    client = NaverTrendClient(json_fetcher=fake_fetcher)
    result = client.validate_session(
        options=NaverTrendOptions(
            service="naver_blog",
            content_type="text",
            auth_cookie="stale_cookie=1",
        )
    )

    assert result["valid"] is True
    assert result["status"] == "authenticated"
    assert result["auth_source"] == "cached_fallback"
    assert result["checked_sources"] == ["inline", "cached_fallback"]
    assert result["topic_group_count"] == 1
    assert result["topic_count"] == 1
    assert calls == [
        ("/accounts/preferred-category/naver_blog", "stale_cookie=1"),
        ("/accounts/preferred-category/naver_blog", "cached_cookie=1"),
    ]


def test_naver_trend_client_validate_session_reports_missing_session(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr("app.collector.naver_trend._LOCAL_SESSION_CACHE_FILE", tmp_path / "missing.json")

    client = NaverTrendClient(json_fetcher=lambda *_args, **_kwargs: {})
    result = client.validate_session(
        options=NaverTrendOptions(
            service="naver_blog",
            content_type="text",
            auth_cookie="",
        )
    )

    assert result["valid"] is False
    assert result["status"] == "missing_session"
    assert result["auth_source"] == "none"
    assert result["checked_sources"] == []
    assert result["topic_group_count"] == 0
    assert result["topic_count"] == 0


def test_naver_trend_validate_session_does_not_report_auth_lock(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr("app.collector.naver_trend._LOCAL_SESSION_CACHE_FILE", tmp_path / "missing.json")
    monkeypatch.setattr("app.collector.naver_trend.wait_for_naver_keyword_request", lambda: None)

    reported_messages: list[str] = []

    def fake_report(message: str) -> None:
        reported_messages.append(message)

    def fake_urlopen(request, timeout=0):
        raise HTTPError(
            request.full_url,
            401,
            "Unauthorized",
            hdrs=None,
            fp=BytesIO(b'{"message":"Unauthorized"}'),
        )

    monkeypatch.setattr("app.collector.naver_trend.report_naver_auth_error", fake_report)
    monkeypatch.setattr("app.collector.naver_trend.urlopen", fake_urlopen)

    client = NaverTrendClient()
    result = client.validate_session(
        options=NaverTrendOptions(
            service="naver_blog",
            content_type="text",
            auth_cookie="NID_AUT=test; NID_SES=session",
        )
    )

    assert result["valid"] is False
    assert result["status"] == "unauthorized"
    assert reported_messages == []


def test_naver_trend_collect_still_reports_auth_lock(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr("app.collector.naver_trend._LOCAL_SESSION_CACHE_FILE", tmp_path / "missing.json")
    monkeypatch.setattr("app.collector.naver_trend.wait_for_naver_keyword_request", lambda: None)

    reported_messages: list[str] = []

    def fake_report(message: str) -> None:
        reported_messages.append(message)

    def fake_urlopen(request, timeout=0):
        raise HTTPError(
            request.full_url,
            401,
            "Unauthorized",
            hdrs=None,
            fp=BytesIO(b'{"message":"Unauthorized"}'),
        )

    monkeypatch.setattr("app.collector.naver_trend.report_naver_auth_error", fake_report)
    monkeypatch.setattr("app.collector.naver_trend.urlopen", fake_urlopen)

    client = NaverTrendClient()
    with pytest.raises(NaverTrendAuthError):
        client.collect_category_keywords(
            topic_name="국내여행",
            options=NaverTrendOptions(
                service="naver_blog",
                content_type="text",
                auth_cookie="NID_AUT=test; NID_SES=session",
            ),
        )

    assert reported_messages == ["Unauthorized"]
