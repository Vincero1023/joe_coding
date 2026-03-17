from __future__ import annotations

from app.expander.utils.tokenizer import normalize_key, normalize_text
from app.title.types import CategoryType


_CATEGORY_PATTERNS: dict[CategoryType, tuple[str, ...]] = {
    "product": ("추천", "리뷰", "후기", "가격", "구매", "모델", "제품"),
    "travel": ("여행", "호텔", "항공", "코스", "숙소", "제주", "부산"),
    "finance": ("보험", "대출", "카드", "지원금", "세금", "투자", "청약"),
    "health": ("건강", "병원", "다이어트", "영양제", "질환", "통증"),
    "real_estate": ("부동산", "아파트", "청약", "분양", "전세", "매매"),
    "food": ("맛집", "카페", "레시피", "빵", "메뉴", "디저트", "떡"),
}



def detect_category(keyword: str) -> CategoryType:
    normalized_keyword = normalize_text(keyword)
    normalized_key = normalize_key(keyword)

    for category, patterns in _CATEGORY_PATTERNS.items():
        if any(pattern in normalized_keyword or normalize_key(pattern) in normalized_key for pattern in patterns):
            return category

    return "general"
