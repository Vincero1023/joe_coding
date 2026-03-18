from __future__ import annotations

import argparse
import json
import traceback
from typing import Any

from app.local.naver_login_browser import LocalLoginBrowserError, LocalNaverLoginBrowserService


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser", default="edge")
    parser.add_argument("--timeout-seconds", type=int, default=300)
    args = parser.parse_args()

    service = LocalNaverLoginBrowserService()
    try:
        result = service.open_and_capture_session(
            browser=str(args.browser),
            timeout_seconds=int(args.timeout_seconds),
            allow_subprocess_fallback=False,
        )
    except LocalLoginBrowserError as exc:
        print(
            json.dumps(
                {
                    "message": str(exc),
                    **exc.to_detail(),
                },
                ensure_ascii=False,
            )
        )
        return 2
    except Exception as exc:  # pragma: no cover - depends on local runtime
        print(
            json.dumps(
                {
                    "message": str(exc) or exc.__class__.__name__,
                    "hint": "보조 프로세스에서 예상하지 못한 오류가 발생했습니다.",
                    "attempts": [],
                    "detail": {
                        "type": exc.__class__.__name__,
                        "traceback": traceback.format_exception(type(exc), exc, exc.__traceback__),
                    },
                },
                ensure_ascii=False,
            )
        )
        return 3

    print(json.dumps(_sanitize_payload(result), ensure_ascii=False))
    return 0


def _sanitize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in payload.items()
        if isinstance(key, str)
    }


if __name__ == "__main__":
    raise SystemExit(main())
