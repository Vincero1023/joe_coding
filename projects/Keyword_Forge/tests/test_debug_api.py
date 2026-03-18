from unittest.mock import patch

from fastapi.testclient import TestClient

from app.collector.service import CollectorService
from app.main import app


client = TestClient(app, raise_server_exceptions=False)


def test_validation_error_returns_structured_payload() -> None:
    response = client.post("/collect", json={"input_data": []})

    assert response.status_code == 422
    assert response.headers["X-Request-ID"]

    payload = response.json()["error"]
    assert payload["code"] == "validation_error"
    assert payload["request_id"] == response.headers["X-Request-ID"]
    assert payload["detail"]["errors"]


def test_internal_error_returns_request_id_and_message() -> None:
    with patch("app.api.routes.collect.collector_module.run", side_effect=RuntimeError("collector crashed")):
        response = client.post("/collect", json={"input_data": {}})

    assert response.status_code == 500
    assert response.headers["X-Request-ID"]

    payload = response.json()["error"]
    assert payload["code"] == "internal_error"
    assert payload["message"] == "collector crashed"
    assert payload["request_id"] == response.headers["X-Request-ID"]
    assert payload["detail"]["type"] == "RuntimeError"


def test_collector_debug_includes_query_failures() -> None:
    def broken_autocomplete(query: str) -> list[str]:
        raise RuntimeError(f"autocomplete failed for {query}")

    service = CollectorService(autocomplete_fetcher=broken_autocomplete)
    with patch.object(service, "_search_naver_results", side_effect=RuntimeError("fallback failed")):
        result = service.run(
            {
                "mode": "category",
                "category": "비즈니스경제",
                "category_source": "preset_search",
                "seed_input": "",
                "options": {
                    "collect_related": False,
                    "collect_autocomplete": True,
                    "collect_bulk": False,
                },
                "debug": True,
            }
        )

    assert result["collected_keywords"] == []

    debug = result["debug"]
    assert debug["summary"]["queries_attempted"] == 1
    assert debug["summary"]["warning_count"] == 2
    assert debug["warnings"][0]["code"] == "autocomplete_error"
    assert debug["warnings"][1]["code"] == "search_fallback_error"
    assert debug["query_logs"][0]["status"] == "warning"
    assert debug["query_logs"][0]["notes"] == ["autocomplete_error", "search_error"]
