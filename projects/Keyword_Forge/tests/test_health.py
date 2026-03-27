from unittest.mock import patch

from app.collector.main import run
from app.collector.naver_trend import NaverTrendCategoryResult, NaverTrendKeyword
from app.collector.service import CollectorService


BUSINESS_CATEGORY = "\ube44\uc988\ub2c8\uc2a4\u00b7\uacbd\uc81c"
DOMESTIC_TRAVEL_CATEGORY = "\uad6d\ub0b4\uc5ec\ud589"
ECONOMY = "\uacbd\uc81c"
ECONOMY_NEWS = "\uacbd\uc81c \ub274\uc2a4"
STARTUP_ITEM = "\ucc3d\uc5c5 \uc544\uc774\ud15c"
SEED_KEYWORD = "\ubc84\ud130\ub5a1"
SEED_AUTOCOMPLETE = "\ubc84\ud130\ub5a1 \ub9db\uc9d1"
SEED_RELATED_A = "\ubc84\ud130\ub5a1 \ub808\uc2dc\ud53c"
SEED_RELATED_B = "\uc11c\uc6b8 \ubc84\ud130\ub5a1"
JEJU_SPECIAL = "\uc81c\uc8fc\ud56d\uacf5 \ud2b9\uac00"
CHERRY_BLOSSOM = "\ubc9a\uaf43\uc5ec\ud589"
CHERRY_BLOSSOM_DATE = "\ubc9a\uaf43\uac1c\ud654\uc2dc\uae30"


def test_collector_collects_keywords_from_requested_category() -> None:
    service = CollectorService(
        autocomplete_fetcher=lambda query: {
            ECONOMY: [ECONOMY_NEWS, STARTUP_ITEM],
        }.get(query, [])
    )

    result = service.run(
        {
            "mode": "category",
            "category": BUSINESS_CATEGORY,
            "category_source": "preset_search",
            "seed_input": "",
            "options": {
                "collect_related": False,
                "collect_autocomplete": True,
                "collect_bulk": False,
            },
        }
    )

    keywords = result["collected_keywords"]
    assert keywords
    assert all(item["category"] == BUSINESS_CATEGORY for item in keywords)
    assert all(set(item) == {"keyword", "category", "source", "raw"} for item in keywords)
    assert all(item["source"] == "naver_autocomplete" for item in keywords)


def test_collector_seed_mode_returns_keyword_source_results() -> None:
    service = CollectorService(
        autocomplete_fetcher=lambda query: {
            SEED_KEYWORD: [SEED_AUTOCOMPLETE],
        }.get(query, []),
        related_fetcher=lambda query: {
            SEED_KEYWORD: [SEED_RELATED_A, SEED_RELATED_B],
        }.get(query, []),
    )

    with patch.object(service, "_search_naver_results", side_effect=AssertionError("seed fallback should not run")):
        seeded = service.run(
            {
                "mode": "seed",
                "category": BUSINESS_CATEGORY,
                "seed_input": SEED_KEYWORD,
                "options": {
                    "collect_related": True,
                    "collect_autocomplete": True,
                    "collect_bulk": False,
                },
                "debug": True,
            }
        )
        autocomplete_only = service.run(
            {
                "mode": "seed",
                "category": BUSINESS_CATEGORY,
                "seed_input": SEED_KEYWORD,
                "options": {
                    "collect_related": False,
                    "collect_autocomplete": True,
                    "collect_bulk": False,
                },
            }
        )

    assert seeded != autocomplete_only
    assert [item["keyword"] for item in seeded["collected_keywords"]] == [
        SEED_AUTOCOMPLETE,
        SEED_RELATED_A,
        SEED_RELATED_B,
    ]
    assert all(item["raw"] == SEED_KEYWORD for item in seeded["collected_keywords"])
    assert {item["source"] for item in seeded["collected_keywords"]} == {"naver_autocomplete", "naver_related"}
    assert all(item["category"] is None for item in seeded["collected_keywords"])
    assert seeded["debug"]["effective_source"] == "seed_keyword_sources"
    assert [item["source"] for item in seeded["debug"]["query_logs"]] == ["naver_autocomplete", "naver_related"]


def test_collector_seed_mode_keeps_direct_seed_when_sources_are_empty() -> None:
    service = CollectorService(
        autocomplete_fetcher=lambda query: [],
        related_fetcher=lambda query: [],
    )

    result = service.run(
        {
            "mode": "seed",
            "category": BUSINESS_CATEGORY,
            "seed_input": "무선 마우스 설정 팁",
            "options": {
                "collect_related": True,
                "collect_autocomplete": True,
                "collect_bulk": False,
            },
            "debug": True,
        }
    )

    assert result["collected_keywords"] == [
        {
            "keyword": "무선 마우스 설정 팁",
            "category": None,
            "source": "seed_input_fallback",
            "raw": "무선 마우스 설정 팁",
        }
    ]
    assert any(warning["code"] == "seed_input_fallback_used" for warning in result["debug"]["warnings"])


def test_collector_returns_empty_when_category_is_not_found() -> None:
    result = run(
        {
            "mode": "category",
            "category": "\uc5c6\ub294\uce74\ud14c\uace0\ub9ac",
            "category_source": "preset_search",
            "seed_input": "",
            "options": {
                "collect_related": False,
                "collect_autocomplete": True,
                "collect_bulk": False,
            },
        }
    )

    assert result["collected_keywords"] == []
    assert result["debug"]["stage"] == "collector"
    assert result["debug"]["summary"]["total_calls"] == 0


def test_collector_category_mode_uses_naver_trend_when_cookie_is_provided() -> None:
    class FakeTrendClient:
        def collect_category_keywords(self, *, topic_name, options):
            assert topic_name == DOMESTIC_TRAVEL_CATEGORY
            assert options.auth_cookie == "cookie=value"
            return NaverTrendCategoryResult(
                topic_name=topic_name,
                topic_id="travel_domestic",
                service=options.service,
                content_type=options.content_type,
                date=options.resolved_date,
                keywords=(
                    NaverTrendKeyword(query=JEJU_SPECIAL, rank=1, rank_change=2),
                    NaverTrendKeyword(query=CHERRY_BLOSSOM, rank=2, rank_change=0),
                    NaverTrendKeyword(query=CHERRY_BLOSSOM_DATE, rank=3, rank_change=None),
                ),
            )

    service = CollectorService(trend_client=FakeTrendClient())
    result = service.run(
        {
            "mode": "category",
            "category": DOMESTIC_TRAVEL_CATEGORY,
            "category_source": "naver_trend",
            "seed_input": "",
            "trend_options": {
                "auth_cookie": "cookie=value",
                "date": "2026-03-16",
                "fallback_to_preset_search": False,
            },
            "options": {
                "collect_related": False,
                "collect_autocomplete": True,
                "collect_bulk": False,
            },
            "debug": True,
        }
    )

    keywords = result["collected_keywords"]
    assert [item["keyword"] for item in keywords] == [JEJU_SPECIAL, CHERRY_BLOSSOM, CHERRY_BLOSSOM_DATE]
    assert all(item["source"] == "naver_trend" for item in keywords)
    assert keywords[0]["rank"] == 1
    assert "rank_change" in keywords[2]
    assert result["debug"]["effective_source"] == "naver_trend"
    assert result["debug"]["trend_topic"] == DOMESTIC_TRAVEL_CATEGORY


def test_collector_naver_trend_falls_back_to_preset_search_without_cookie(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "app.collector.naver_trend._LOCAL_SESSION_CACHE_FILE",
        tmp_path / "missing_naver_creator_session.json",
    )
    service = CollectorService(
        autocomplete_fetcher=lambda query: {
            "\uad6d\ub0b4 \uc5ec\ud589": ["\uad6d\ub0b4 \uc5ec\ud589 \ucd94\ucc9c", "\uad6d\ub0b4 \uc5ec\ud589 \ucf54\uc2a4"],
        }.get(query, [])
    )

    result = service.run(
        {
            "mode": "category",
            "category": DOMESTIC_TRAVEL_CATEGORY,
            "category_source": "naver_trend",
            "seed_input": "",
            "trend_options": {
                "auth_cookie": "",
                "fallback_to_preset_search": True,
            },
            "options": {
                "collect_related": False,
                "collect_autocomplete": True,
                "collect_bulk": False,
            },
            "debug": True,
        }
    )

    assert [item["source"] for item in result["collected_keywords"]] == [
        "naver_autocomplete",
        "naver_autocomplete",
    ]
    assert result["debug"]["effective_source"] == "preset_search"
    assert result["debug"]["warnings"][0]["code"] == "naver_trend_auth_required"
    assert result["debug"]["query_logs"][0]["source"] == "naver_trend"
    assert result["debug"]["query_logs"][1]["source"] == "naver_autocomplete"
