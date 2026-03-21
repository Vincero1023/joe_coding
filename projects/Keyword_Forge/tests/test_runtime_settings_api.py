import pytest
from fastapi.testclient import TestClient

from app.core.runtime_settings import reset_runtime_operation_settings_for_tests
from app.main import app


client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_runtime_settings() -> None:
    reset_runtime_operation_settings_for_tests()
    yield
    reset_runtime_operation_settings_for_tests()


def test_runtime_settings_endpoint_reads_and_updates_snapshot() -> None:
    response = client.get("/settings/runtime")

    assert response.status_code == 200
    assert response.json()["operation_settings"]["settings"]["mode"] == "always_on_slow"

    update_response = client.post(
        "/settings/runtime",
        json={
            "mode": "custom",
            "naver_request_gap_seconds": 5.5,
            "daily_operation_limit": 12,
            "daily_naver_request_limit": 150,
            "max_continuous_minutes": 45,
            "stop_on_auth_error": True,
        },
    )

    assert update_response.status_code == 200
    payload = update_response.json()["operation_settings"]
    assert payload["settings"]["mode"] == "custom"
    assert payload["settings"]["naver_request_gap_seconds"] == 5.5
    assert payload["settings"]["daily_operation_limit"] == 12


def test_daily_operation_limit_guard_returns_429() -> None:
    client.post(
        "/settings/runtime",
        json={
            "mode": "custom",
            "naver_request_gap_seconds": 0,
            "daily_operation_limit": 1,
            "daily_naver_request_limit": 0,
            "max_continuous_minutes": 0,
            "stop_on_auth_error": True,
        },
    )

    first = client.post("/analyze", json={"input_data": {"keywords_text": "보험 추천"}})
    second = client.post("/analyze", json={"input_data": {"keywords_text": "보험 비교"}})

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["error"]["code"] == "daily_operation_limit_reached"
