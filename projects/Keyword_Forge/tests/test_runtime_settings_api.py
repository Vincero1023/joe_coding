import pytest
from fastapi.testclient import TestClient

from app.core.runtime_settings import reset_runtime_operation_settings_for_tests
from app.core.title_prompt_settings import (
    reset_title_prompt_settings_for_tests,
    set_title_prompt_settings_path_for_tests,
)
from app.main import app


client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_runtime_settings() -> None:
    reset_runtime_operation_settings_for_tests()
    yield
    reset_runtime_operation_settings_for_tests()


@pytest.fixture(autouse=True)
def isolate_title_prompt_settings(tmp_path) -> None:
    set_title_prompt_settings_path_for_tests(tmp_path / "settings" / "title_prompt_settings.json")
    yield
    reset_title_prompt_settings_for_tests()


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


def test_title_prompt_settings_endpoint_reads_and_writes_repo_backed_settings(tmp_path) -> None:
    response = client.get("/settings/title-prompt")

    assert response.status_code == 200
    assert response.json()["title_prompt_settings"]["prompt_profiles"] == []
    assert response.json()["title_prompt_settings"]["preset_profiles"] == []

    update_response = client.post(
        "/settings/title-prompt",
        json={
            "preset_key": "openai_balanced",
            "direct_system_prompt": "제목은 더 구체적으로 작성한다.",
            "system_prompt": "제목은 더 구체적으로 작성한다.",
            "prompt_profiles": [
                {
                    "id": "profile-1",
                    "name": "공유 저장본",
                    "prompt": "비교 포인트를 먼저 보여준다.",
                    "updated_at": "2026-03-25T21:30:00+09:00",
                }
            ],
            "active_prompt_profile_id": "profile-1",
        },
    )

    assert update_response.status_code == 200
    payload = update_response.json()["title_prompt_settings"]
    assert payload["preset_key"] == "openai_balanced"
    assert payload["active_prompt_profile_id"] == "profile-1"
    assert payload["system_prompt"] == "비교 포인트를 먼저 보여준다."

    saved_path = tmp_path / "settings" / "title_prompt_settings.json"
    assert saved_path.exists()
    assert "공유 저장본" in saved_path.read_text(encoding="utf-8")

def test_title_prompt_settings_endpoint_persists_custom_preset_profiles() -> None:
    response = client.post(
        "/settings/title-prompt",
        json={
            "preset_profiles": [
                {
                    "id": "preset-1",
                    "name": "custom preset",
                    "provider": "openai",
                    "model": "gpt-4.1-mini",
                    "temperature": 0.7,
                    "issue_context_enabled": True,
                    "issue_context_limit": 3,
                    "issue_source_mode": "mixed",
                    "community_sources": ["cafe.naver.com"],
                    "community_custom_domains": ["clien.net"],
                    "prompt_profile_id": "profile-1",
                    "direct_system_prompt": "custom prompt",
                    "rewrite_provider": "vertex",
                    "rewrite_model": "gemini-2.5-flash-lite",
                }
            ],
            "active_preset_profile_id": "preset-1",
        },
    )

    assert response.status_code == 200
    payload = response.json()["title_prompt_settings"]
    assert payload["active_preset_profile_id"] == "preset-1"
    assert payload["preset_profiles"][0]["rewrite_provider"] == "vertex"
    assert payload["preset_profiles"][0]["community_custom_domains"] == ["clien.net"]


def test_title_prompt_settings_partial_update_preserves_custom_preset_profiles() -> None:
    client.post(
        "/settings/title-prompt",
        json={
            "preset_profiles": [
                {
                    "id": "preset-1",
                    "name": "custom preset",
                    "provider": "openai",
                    "model": "gpt-4o-mini",
                    "temperature": 0.7,
                }
            ],
            "active_preset_profile_id": "preset-1",
        },
    )

    response = client.post(
        "/settings/title-prompt",
        json={
            "direct_system_prompt": "updated prompt only",
            "system_prompt": "updated prompt only",
        },
    )

    assert response.status_code == 200
    payload = response.json()["title_prompt_settings"]
    assert payload["direct_system_prompt"] == "updated prompt only"
    assert payload["active_preset_profile_id"] == "preset-1"
    assert payload["preset_profiles"][0]["id"] == "preset-1"


def test_title_prompt_settings_endpoint_persists_evaluation_prompt_profiles() -> None:
    response = client.post(
        "/settings/title-prompt",
        json={
            "evaluation_direct_prompt": "direct eval prompt",
            "evaluation_prompt": "direct eval prompt",
            "evaluation_prompt_profiles": [
                {
                    "id": "eval-profile-1",
                    "name": "home ctr",
                    "prompt": "custom home ctr prompt",
                    "updated_at": "2026-03-26T09:00:00+09:00",
                }
            ],
            "active_evaluation_prompt_profile_id": "eval-profile-1",
        },
    )

    assert response.status_code == 200
    payload = response.json()["title_prompt_settings"]
    assert payload["active_evaluation_prompt_profile_id"] == "eval-profile-1"
    assert payload["evaluation_prompt"] == "custom home ctr prompt"
    assert payload["evaluation_prompt_profiles"][0]["name"] == "home ctr"


def test_title_prompt_settings_endpoint_persists_evaluation_prompt_in_custom_preset() -> None:
    response = client.post(
        "/settings/title-prompt",
        json={
            "preset_profiles": [
                {
                    "id": "preset-1",
                    "name": "custom preset",
                    "provider": "openai",
                    "model": "gpt-4.1-mini",
                    "temperature": 0.7,
                    "evaluation_prompt_profile_id": "eval-profile-1",
                    "evaluation_direct_prompt": "custom eval prompt",
                }
            ],
            "active_preset_profile_id": "preset-1",
        },
    )

    assert response.status_code == 200
    payload = response.json()["title_prompt_settings"]
    assert payload["preset_profiles"][0]["evaluation_prompt_profile_id"] == "eval-profile-1"
    assert payload["preset_profiles"][0]["evaluation_direct_prompt"] == "custom eval prompt"
