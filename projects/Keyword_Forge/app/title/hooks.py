from __future__ import annotations

from app.title.types import TriggerBundle


_TIME_TRIGGERS = ("어제", "방금", "이번주", "올해")
_CURIOSITY_TRIGGERS = ("왜 이럴까", "알고 보니", "진짜일까")
_CONTRAST_TRIGGERS = ("비교해보니", "더 좋은 쪽", "결과가 달랐다")
_NUMERIC_TRIGGERS = ("3가지", "7일", "10%", "2026")
_OPPORTUNITY_TRIGGERS = ("기회일까", "놓치면 손해", "지금 봐야 할 이유")



def build_trigger_bundle(keyword: str) -> TriggerBundle:
    seed = sum(ord(char) for char in keyword)
    return TriggerBundle(
        time=_TIME_TRIGGERS[seed % len(_TIME_TRIGGERS)],
        curiosity=_CURIOSITY_TRIGGERS[seed % len(_CURIOSITY_TRIGGERS)],
        contrast=_CONTRAST_TRIGGERS[seed % len(_CONTRAST_TRIGGERS)],
        numeric=_NUMERIC_TRIGGERS[seed % len(_NUMERIC_TRIGGERS)],
        opportunity=_OPPORTUNITY_TRIGGERS[seed % len(_OPPORTUNITY_TRIGGERS)],
    )
