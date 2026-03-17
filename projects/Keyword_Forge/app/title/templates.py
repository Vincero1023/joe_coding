from __future__ import annotations

from app.expander.utils.tokenizer import normalize_text
from app.title.hooks import build_trigger_bundle
from app.title.rules import NAVER_HOME_MAX_LENGTH, YEAR_TEXT
from app.title.types import CategoryType, TriggerBundle



def build_naver_home_titles(keyword: str, category: CategoryType) -> list[str]:
    triggers = build_trigger_bundle(keyword)
    candidates = _naver_home_candidates(keyword, category, triggers)
    return _select_unique_titles(candidates, limit=2, max_length=NAVER_HOME_MAX_LENGTH)



def build_blog_titles(keyword: str, category: CategoryType) -> list[str]:
    triggers = build_trigger_bundle(keyword)
    candidates = _blog_candidates(keyword, category, triggers)
    return _select_unique_titles(candidates, limit=2)



def _naver_home_candidates(keyword: str, category: CategoryType, triggers: TriggerBundle) -> list[str]:
    detail = _category_naver_detail(category)
    return [
        f"{triggers.time} {keyword} 갑자기 바뀌었다, 이유가 이상하다",
        f"{keyword} 비교해봤다, 결과가 예상과 달랐다",
        f"{keyword} 지금 선택 갈린다, 더 좋은 쪽은 따로 있었다",
        f"{keyword} 차이 {triggers.numeric} 벌어졌다, 생각보다 컸다",
        f"{triggers.time} {keyword} 흐름 바뀌었다, 지금이 기회일까",
        f"{keyword} 놓치면 손해, 이번주 기준이 달라졌다",
        f"{triggers.time} {keyword} {detail}, {triggers.curiosity}",
        f"{keyword} {detail}, {triggers.opportunity}",
    ]



def _blog_candidates(keyword: str, category: CategoryType, triggers: TriggerBundle) -> list[str]:
    detail = _category_blog_detail(category)
    return [
        f"{keyword} 완벽 정리 ({YEAR_TEXT})",
        f"{keyword} 비교 및 선택 기준 정리",
        f"{keyword} 가격, 후기, 추천 한 번에 정리",
        f"{keyword} 실제 기준 달라졌다, 지금 확인할 것",
        f"{keyword} 선택 전 꼭 봐야 할 포인트 {triggers.numeric}",
        f"{keyword} {detail} 한 번에 정리",
    ]



def _select_unique_titles(candidates: list[str], limit: int, max_length: int | None = None) -> list[str]:
    selected: list[str] = []
    seen: set[str] = set()

    for candidate in candidates:
        title = normalize_text(candidate).replace(":", "")
        if not title or title in seen:
            continue
        if max_length is not None and len(title) > max_length:
            title = title[:max_length].rstrip()
        if title in seen or not title:
            continue
        seen.add(title)
        selected.append(title)
        if len(selected) >= limit:
            break

    return selected



def _category_naver_detail(category: CategoryType) -> str:
    phrases = {
        "product": "가격 차이 생각보다 컸다",
        "travel": "혼잡도와 시간 차이 벌어졌다",
        "finance": "가입 기준과 조건 달라졌다",
        "health": "주의할 변화가 생각보다 컸다",
        "real_estate": "경쟁률과 거래량 흐름 달라졌다",
        "food": "반응과 시간 차이 꽤 컸다",
        "general": "흐름이 예상보다 달라졌다",
    }
    return phrases.get(category, "흐름이 예상보다 달라졌다")



def _category_blog_detail(category: CategoryType) -> str:
    phrases = {
        "product": "가격, 후기, 성능 차이",
        "travel": "혼잡도, 루트, 시간 포인트",
        "finance": "금리, 가입 기준, 조건 차이",
        "health": "주의, 변화, 차이 포인트",
        "real_estate": "청약, 경쟁률, 거래량 기준",
        "food": "반응, 시간, 맛 차이",
        "general": "핵심 기준과 체크 포인트",
    }
    return phrases.get(category, "핵심 기준과 체크 포인트")
