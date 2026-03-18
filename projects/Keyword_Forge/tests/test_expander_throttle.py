from app.expander.utils.throttle import RequestThrottle, get_naver_request_gap_seconds


def test_request_throttle_spaces_calls_for_same_bucket(monkeypatch) -> None:
    state = {"now": 100.0}
    sleeps: list[float] = []

    def fake_monotonic() -> float:
        return state["now"]

    def fake_sleep(delay: float) -> None:
        sleeps.append(delay)
        state["now"] += delay

    monkeypatch.setattr("app.expander.utils.throttle.time.monotonic", fake_monotonic)
    monkeypatch.setattr("app.expander.utils.throttle.time.sleep", fake_sleep)

    throttle = RequestThrottle(default_min_interval_seconds=0.5)

    throttle.wait("naver")
    throttle.wait("naver")
    throttle.wait("other")

    assert sleeps == [0.5]


def test_get_naver_request_gap_seconds_reads_env_override(monkeypatch) -> None:
    monkeypatch.setenv("KEYWORD_FORGE_NAVER_REQUEST_GAP_SECONDS", "0.8")

    assert get_naver_request_gap_seconds() == 0.8
