from __future__ import annotations

from app.expander.utils.tokenizer import normalize_key, normalize_text
from app.title.types import CategoryType


_CATEGORY_PATTERNS: dict[CategoryType, tuple[str, ...]] = {
    "product": (
        "가격",
        "구매",
        "모델",
        "제품",
        "브랜드",
        "언박싱",
        "후기",
        "쿠폰",
        "할인",
        "평점",
        "사양",
        "용량",
        "컬러",
        "배터리",
        "칩셋",
        "성능",
        "마우스",
        "키보드",
        "노트북",
        "맥북",
        "아이패드",
        "아이폰",
        "갤럭시",
        "이어폰",
        "헤드셋",
        "모니터",
        "스피커",
        "웹캠",
        "프린터",
        "공유기",
        "태블릿",
        "닌텐도",
        "스위치",
        "콘솔",
        "카메라",
    ),
    "travel": (
        "여행",
        "호텔",
        "항공",
        "숙소",
        "패스",
        "루트",
        "축제",
        "캠핑",
        "등산",
        "투어",
        "렌터카",
        "코스",
        "제주",
        "부산",
    ),
    "finance": (
        "보험",
        "대출",
        "카드",
        "계좌",
        "isa",
        "지원금",
        "세금",
        "투자",
        "지수",
        "선물",
        "야간선물",
        "실시간",
        "시세",
        "금시세",
        "금값",
        "국제금",
        "코스피",
        "코스닥",
        "나스닥",
        "금리",
        "환율",
        "업종",
        "실적",
        "컨센서스",
        "etf",
        "리밸런싱",
        "주식",
        "증시",
    ),
    "health": (
        "기초연금",
        "장기요양",
        "복지",
        "돌봄",
        "낙상",
        "연하",
        "보청기",
        "보조기구",
        "건강",
        "병원",
        "다이어트",
        "영양제",
        "질환",
        "통증",
    ),
    "real_estate": (
        "부동산",
        "아파트",
        "청약",
        "분양",
        "미분양",
        "전세",
        "월세",
        "전월세",
        "재건축",
        "거래량",
        "전망지수",
        "gtx",
        "신도시",
        "공공분양",
        "매매",
    ),
    "food": (
        "맛집",
        "카페",
        "레시피",
        "영양",
        "칼로리",
        "단백질",
        "나트륨",
        "외식",
        "간식",
        "대체식",
        "빵",
        "메뉴",
        "디저트",
        "떡",
    ),
}

_CATEGORY_PRIORITY: tuple[CategoryType, ...] = (
    "finance",
    "real_estate",
    "travel",
    "health",
    "food",
    "product",
)



def detect_category(keyword: str) -> CategoryType:
    normalized_keyword = normalize_text(keyword)
    normalized_key = normalize_key(keyword)
    if not normalized_keyword:
        return "general"

    matches = {
        category: _count_matches(normalized_keyword, normalized_key, patterns)
        for category, patterns in _CATEGORY_PATTERNS.items()
    }
    best_score = max(matches.values(), default=0)
    if best_score <= 0:
        return "general"

    for category in _CATEGORY_PRIORITY:
        if matches.get(category) == best_score:
            return category

    return "general"


def _count_matches(keyword: str, keyword_key: str, patterns: tuple[str, ...]) -> int:
    return sum(
        1
        for pattern in patterns
        if pattern in keyword or normalize_key(pattern) in keyword_key
    )
