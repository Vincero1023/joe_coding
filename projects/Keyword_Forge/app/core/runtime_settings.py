from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo


_KST = ZoneInfo("Asia/Seoul")
_IDLE_RESET_MINUTES = 20


@dataclass(frozen=True)
class OperationModePreset:
    key: str
    label: str
    description: str
    naver_request_gap_seconds: float
    daily_operation_limit: int
    daily_naver_request_limit: int
    max_continuous_minutes: int
    stop_on_auth_error: bool


@dataclass(frozen=True)
class RuntimeOperationSettings:
    mode: str
    naver_request_gap_seconds: float
    daily_operation_limit: int
    daily_naver_request_limit: int
    max_continuous_minutes: int
    stop_on_auth_error: bool


@dataclass
class RuntimeGuardState:
    day_key: str
    operations_started: int = 0
    naver_requests_started: int = 0
    active_window_started_at: float = 0.0
    last_naver_request_at: float = 0.0
    last_operation_name: str = ""
    last_operation_at: float = 0.0
    auth_lock_active: bool = False
    auth_lock_message: str = ""
    auth_lock_started_at: float = 0.0


class RuntimeGuardError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "runtime_guard",
        detail: dict[str, Any] | None = None,
        status_code: int = 429,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.detail = detail or {}
        self.status_code = int(status_code)


_MODE_PRESETS: dict[str, OperationModePreset] = {
    "daily_light": OperationModePreset(
        key="daily_light",
        label="일일 10회 이하",
        description="하루 작업 수를 낮게 묶고 요청을 크게 띄워 IP 부담을 줄이는 모드입니다.",
        naver_request_gap_seconds=8.0,
        daily_operation_limit=10,
        daily_naver_request_limit=120,
        max_continuous_minutes=30,
        stop_on_auth_error=True,
    ),
    "always_on_slow": OperationModePreset(
        key="always_on_slow",
        label="상시 슬로우",
        description="장시간 돌려도 기본 간격을 유지하면서 인증 오류는 바로 멈추는 모드입니다.",
        naver_request_gap_seconds=2.0,
        daily_operation_limit=0,
        daily_naver_request_limit=0,
        max_continuous_minutes=180,
        stop_on_auth_error=True,
    ),
}
_DEFAULT_MODE_KEY = "always_on_slow"
_CUSTOM_MODE_KEY = "custom"


def _today_key() -> str:
    return datetime.now(_KST).date().isoformat()


def _now_monotonic() -> float:
    return time.monotonic()


def _normalize_mode(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in _MODE_PRESETS or normalized == _CUSTOM_MODE_KEY:
        return normalized
    return _DEFAULT_MODE_KEY


def _preset_settings(mode_key: str) -> RuntimeOperationSettings:
    preset = _MODE_PRESETS[_normalize_mode(mode_key)]
    return RuntimeOperationSettings(
        mode=preset.key,
        naver_request_gap_seconds=preset.naver_request_gap_seconds,
        daily_operation_limit=preset.daily_operation_limit,
        daily_naver_request_limit=preset.daily_naver_request_limit,
        max_continuous_minutes=preset.max_continuous_minutes,
        stop_on_auth_error=preset.stop_on_auth_error,
    )


def _coerce_float(value: Any, *, default: float, minimum: float = 0.0, maximum: float = 300.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def _coerce_int(value: Any, *, default: int, minimum: int = 0, maximum: int = 100000) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def _normalize_settings(raw: Any) -> RuntimeOperationSettings:
    if not isinstance(raw, dict):
        raw = {}

    mode = _normalize_mode(raw.get("mode"))
    if mode in _MODE_PRESETS:
        return _preset_settings(mode)

    base = _preset_settings(_DEFAULT_MODE_KEY)
    return RuntimeOperationSettings(
        mode=_CUSTOM_MODE_KEY,
        naver_request_gap_seconds=_coerce_float(
            raw.get("naver_request_gap_seconds"),
            default=base.naver_request_gap_seconds,
            minimum=0.0,
            maximum=120.0,
        ),
        daily_operation_limit=_coerce_int(
            raw.get("daily_operation_limit"),
            default=base.daily_operation_limit,
            minimum=0,
            maximum=1000,
        ),
        daily_naver_request_limit=_coerce_int(
            raw.get("daily_naver_request_limit"),
            default=base.daily_naver_request_limit,
            minimum=0,
            maximum=100000,
        ),
        max_continuous_minutes=_coerce_int(
            raw.get("max_continuous_minutes"),
            default=base.max_continuous_minutes,
            minimum=0,
            maximum=24 * 60,
        ),
        stop_on_auth_error=bool(raw.get("stop_on_auth_error", base.stop_on_auth_error)),
    )


class RuntimeSettingsStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._settings = _preset_settings(_DEFAULT_MODE_KEY)
        self._state = RuntimeGuardState(day_key=_today_key())

    def get_settings(self) -> RuntimeOperationSettings:
        with self._lock:
            return RuntimeOperationSettings(**asdict(self._settings))

    def update_settings(self, raw: Any) -> RuntimeOperationSettings:
        normalized = _normalize_settings(raw)
        with self._lock:
            self._settings = normalized
            self._rollover_day_locked()
            self._clear_auth_lock_locked()
            return RuntimeOperationSettings(**asdict(self._settings))

    def get_snapshot(self) -> dict[str, Any]:
        with self._lock:
            self._rollover_day_locked()
            settings = RuntimeOperationSettings(**asdict(self._settings))
            state = RuntimeGuardState(**asdict(self._state))

        now = _now_monotonic()
        active_window_minutes = 0
        if state.active_window_started_at > 0 and state.last_naver_request_at > 0:
            active_window_minutes = int(max(0.0, now - state.active_window_started_at) // 60)

        daily_operation_remaining = None
        if settings.daily_operation_limit > 0:
            daily_operation_remaining = max(settings.daily_operation_limit - state.operations_started, 0)

        daily_request_remaining = None
        if settings.daily_naver_request_limit > 0:
            daily_request_remaining = max(settings.daily_naver_request_limit - state.naver_requests_started, 0)

        return {
            "settings": asdict(settings),
            "state": {
                "day_key": state.day_key,
                "operations_started": state.operations_started,
                "daily_operation_remaining": daily_operation_remaining,
                "naver_requests_started": state.naver_requests_started,
                "daily_naver_request_remaining": daily_request_remaining,
                "active_window_minutes": active_window_minutes,
                "last_operation_name": state.last_operation_name,
                "auth_lock_active": state.auth_lock_active,
                "auth_lock_message": state.auth_lock_message,
            },
            "presets": [asdict(preset) for preset in _MODE_PRESETS.values()],
        }

    def reset_guards(self) -> dict[str, Any]:
        with self._lock:
            self._rollover_day_locked()
            self._clear_auth_lock_locked()
        return self.get_snapshot()

    def reset_all(self) -> None:
        with self._lock:
            self._settings = _preset_settings(_DEFAULT_MODE_KEY)
            self._state = RuntimeGuardState(day_key=_today_key())

    def ensure_naver_auth_unlocked(self) -> None:
        with self._lock:
            self._rollover_day_locked()
            self._raise_auth_lock_if_needed_locked()

    def record_operation_start(self, operation_name: str) -> None:
        safe_name = str(operation_name or "").strip() or "manual_run"
        with self._lock:
            self._rollover_day_locked()
            if (
                self._settings.daily_operation_limit > 0
                and self._state.operations_started >= self._settings.daily_operation_limit
            ):
                raise RuntimeGuardError(
                    "오늘 작업 시작 한도를 초과했습니다. 설정창에서 운영 모드를 바꾸거나 내일 다시 실행하세요.",
                    code="daily_operation_limit_reached",
                    detail={
                        "limit": self._settings.daily_operation_limit,
                        "operations_started": self._state.operations_started,
                        "operation_name": safe_name,
                    },
                )

            self._state.operations_started += 1
            self._state.last_operation_name = safe_name
            self._state.last_operation_at = _now_monotonic()

    def before_naver_request(self) -> None:
        now = _now_monotonic()
        with self._lock:
            self._rollover_day_locked()
            self._raise_auth_lock_if_needed_locked()

            if (
                self._settings.daily_naver_request_limit > 0
                and self._state.naver_requests_started >= self._settings.daily_naver_request_limit
            ):
                raise RuntimeGuardError(
                    "오늘 Naver 요청 예산을 모두 사용했습니다. 설정창에서 상한을 조정하거나 내일 다시 실행하세요.",
                    code="daily_naver_request_limit_reached",
                    detail={
                        "limit": self._settings.daily_naver_request_limit,
                        "naver_requests_started": self._state.naver_requests_started,
                    },
                )

            if (
                self._state.last_naver_request_at <= 0
                or (now - self._state.last_naver_request_at) >= (_IDLE_RESET_MINUTES * 60)
            ):
                self._state.active_window_started_at = now

            if (
                self._settings.max_continuous_minutes > 0
                and self._state.active_window_started_at > 0
                and (now - self._state.active_window_started_at) >= (self._settings.max_continuous_minutes * 60)
            ):
                raise RuntimeGuardError(
                    "연속 실행 보호가 동작해 Naver 요청을 잠시 멈췄습니다. 잠시 쉬었다가 다시 실행하세요.",
                    code="continuous_runtime_limit_reached",
                    detail={"max_continuous_minutes": self._settings.max_continuous_minutes},
                )

            self._state.naver_requests_started += 1
            self._state.last_naver_request_at = now
            if self._state.active_window_started_at <= 0:
                self._state.active_window_started_at = now

    def report_auth_error(self, message: str) -> None:
        with self._lock:
            if not self._settings.stop_on_auth_error:
                return
            self._state.auth_lock_active = True
            self._state.auth_lock_message = str(message or "").strip() or (
                "401/403 응답이 감지되어 보호 잠금을 걸었습니다. 세션을 확인한 뒤 잠금을 해제하세요."
            )
            self._state.auth_lock_started_at = _now_monotonic()

    def _rollover_day_locked(self) -> None:
        today_key = _today_key()
        if self._state.day_key == today_key:
            return
        self._state = RuntimeGuardState(day_key=today_key)

    def _clear_auth_lock_locked(self) -> None:
        self._state.auth_lock_active = False
        self._state.auth_lock_message = ""
        self._state.auth_lock_started_at = 0.0

    def _raise_auth_lock_if_needed_locked(self) -> None:
        if not self._settings.stop_on_auth_error or not self._state.auth_lock_active:
            return

        raise RuntimeGuardError(
            "이전 인증 오류로 보호 잠금이 활성화되어 요청을 중지했습니다. 운영 설정에서 잠금을 해제한 뒤 다시 실행하세요.",
            code="auth_guard_locked",
            detail={
                "auth_lock_active": True,
                "auth_lock_message": self._state.auth_lock_message,
            },
            status_code=423,
        )


_STORE = RuntimeSettingsStore()


def get_runtime_operation_settings() -> RuntimeOperationSettings:
    return _STORE.get_settings()


def update_runtime_operation_settings(raw: Any) -> RuntimeOperationSettings:
    return _STORE.update_settings(raw)


def get_runtime_operation_snapshot() -> dict[str, Any]:
    return _STORE.get_snapshot()


def reset_runtime_operation_guards() -> dict[str, Any]:
    return _STORE.reset_guards()


def record_operation_start(operation_name: str) -> None:
    _STORE.record_operation_start(operation_name)


def before_naver_request() -> None:
    _STORE.before_naver_request()


def ensure_naver_auth_unlocked() -> None:
    _STORE.ensure_naver_auth_unlocked()


def report_naver_auth_error(message: str) -> None:
    _STORE.report_auth_error(message)


def reset_runtime_operation_settings_for_tests() -> None:
    _STORE.reset_all()
