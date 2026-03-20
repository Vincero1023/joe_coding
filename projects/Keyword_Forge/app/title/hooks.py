from __future__ import annotations

from app.title.types import TriggerBundle


_TIME_TRIGGERS = ("오늘", "이번주", "최근", "2026")
_CURIOSITY_TRIGGERS = ("어디서 갈릴까", "핵심은 뭘까", "먼저 볼 부분", "왜 찾는지")
_CONTRAST_TRIGGERS = ("비교 포인트", "선택 기준", "차이 정리", "체크 포인트")
_NUMERIC_TRIGGERS = ("3가지", "5분", "체크리스트", "2026")
_OPPORTUNITY_TRIGGERS = ("지금 확인할 포인트", "먼저 볼 이유", "실수 줄이는 법", "핵심만 보기")



def build_trigger_bundle(keyword: str) -> TriggerBundle:
    seed = sum(ord(char) for char in keyword)
    return TriggerBundle(
        time=_TIME_TRIGGERS[seed % len(_TIME_TRIGGERS)],
        curiosity=_CURIOSITY_TRIGGERS[seed % len(_CURIOSITY_TRIGGERS)],
        contrast=_CONTRAST_TRIGGERS[seed % len(_CONTRAST_TRIGGERS)],
        numeric=_NUMERIC_TRIGGERS[seed % len(_NUMERIC_TRIGGERS)],
        opportunity=_OPPORTUNITY_TRIGGERS[seed % len(_OPPORTUNITY_TRIGGERS)],
    )
