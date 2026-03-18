import json

from app.collector.categories import CATEGORY_CHOICES, resolve_category_name
from app.collector.naver_trend import (
    NaverTrendAuthError,
    NaverTrendClient,
    NaverTrendOptions,
)


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
