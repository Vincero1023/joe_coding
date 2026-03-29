import pytest

from app.core.runtime_settings import (
    RuntimeGuardError,
    before_naver_request,
    ensure_naver_auth_unlocked,
    get_runtime_operation_snapshot,
    record_operation_start,
    report_naver_auth_error,
    reset_runtime_operation_settings_for_tests,
    update_runtime_operation_settings,
)


@pytest.fixture(autouse=True)
def reset_runtime_settings() -> None:
    reset_runtime_operation_settings_for_tests()
    yield
    reset_runtime_operation_settings_for_tests()


def test_runtime_settings_default_snapshot_uses_always_on_slow() -> None:
    snapshot = get_runtime_operation_snapshot()

    assert snapshot["settings"]["mode"] == "always_on_slow"
    assert snapshot["settings"]["naver_request_gap_seconds"] == 2.0
    assert snapshot["state"]["operations_started"] == 0


def test_update_runtime_settings_applies_daily_light_preset() -> None:
    update_runtime_operation_settings({"mode": "daily_light"})

    snapshot = get_runtime_operation_snapshot()

    assert snapshot["settings"]["mode"] == "daily_light"
    assert snapshot["settings"]["daily_operation_limit"] == 10
    assert snapshot["settings"]["daily_naver_request_limit"] == 120


def test_daily_operation_limit_blocks_extra_runs() -> None:
    update_runtime_operation_settings(
        {
            "mode": "custom",
            "naver_request_gap_seconds": 0,
            "daily_operation_limit": 1,
            "daily_naver_request_limit": 0,
            "max_continuous_minutes": 0,
            "stop_on_auth_error": True,
        }
    )

    record_operation_start("collect")

    with pytest.raises(RuntimeGuardError) as excinfo:
        record_operation_start("collect")

    assert excinfo.value.code == "daily_operation_limit_reached"


def test_daily_naver_request_limit_blocks_extra_attempts() -> None:
    update_runtime_operation_settings(
        {
            "mode": "custom",
            "naver_request_gap_seconds": 0,
            "daily_operation_limit": 0,
            "daily_naver_request_limit": 1,
            "max_continuous_minutes": 0,
            "stop_on_auth_error": True,
        }
    )

    before_naver_request()

    with pytest.raises(RuntimeGuardError) as excinfo:
        before_naver_request()

    assert excinfo.value.code == "daily_naver_request_limit_reached"


def test_auth_error_lock_blocks_follow_up_requests() -> None:
    update_runtime_operation_settings(
        {
            "mode": "custom",
            "naver_request_gap_seconds": 0,
            "daily_operation_limit": 0,
            "daily_naver_request_limit": 0,
            "max_continuous_minutes": 0,
            "stop_on_auth_error": True,
        }
    )
    report_naver_auth_error("creator session expired")

    with pytest.raises(RuntimeGuardError) as excinfo:
        before_naver_request()

    assert excinfo.value.code == "auth_guard_locked"
    assert excinfo.value.status_code == 423
    assert "보호 잠금" in str(excinfo.value)
    assert excinfo.value.detail["auth_lock_active"] is True
    assert excinfo.value.detail["auth_lock_message"] == "creator session expired"


def test_ensure_naver_auth_unlocked_does_not_consume_request_budget() -> None:
    update_runtime_operation_settings(
        {
            "mode": "custom",
            "naver_request_gap_seconds": 0,
            "daily_operation_limit": 0,
            "daily_naver_request_limit": 0,
            "max_continuous_minutes": 0,
            "stop_on_auth_error": True,
        }
    )
    report_naver_auth_error("creator session expired")

    with pytest.raises(RuntimeGuardError) as excinfo:
        ensure_naver_auth_unlocked()

    snapshot = get_runtime_operation_snapshot()

    assert excinfo.value.code == "auth_guard_locked"
    assert snapshot["state"]["naver_requests_started"] == 0
