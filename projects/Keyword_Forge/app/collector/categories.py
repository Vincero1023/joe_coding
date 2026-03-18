from __future__ import annotations

import re


CATEGORY_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "엔터테인먼트·예술",
        (
            "문학·책",
            "영화",
            "미술·디자인",
            "공연·전시",
            "음악",
            "드라마",
            "스타·연예인",
            "만화·애니",
            "방송",
        ),
    ),
    (
        "생활·노하우·쇼핑",
        (
            "일상·생각",
            "육아·결혼",
            "반려동물",
            "좋은글·이미지",
            "패션·미용",
            "인테리어·DIY",
            "요리·레시피",
            "상품리뷰",
            "원예·재배",
        ),
    ),
    (
        "취미·여가·여행",
        (
            "게임",
            "스포츠",
            "사진",
            "자동차",
            "취미",
            "국내여행",
            "세계여행",
            "맛집",
        ),
    ),
    (
        "지식·동향",
        (
            "IT·컴퓨터",
            "사회·정치",
            "건강·의학",
            "비즈니스·경제",
            "어학·외국어",
            "교육·학문",
        ),
    ),
)

CATEGORY_CHOICES = tuple(category for _, categories in CATEGORY_GROUPS for category in categories)

CATEGORY_QUERIES: dict[str, tuple[str, ...]] = {
    "문학·책": ("책 추천", "소설", "에세이"),
    "영화": ("영화", "영화 추천", "넷플릭스 영화"),
    "미술·디자인": ("디자인", "전시", "브랜딩"),
    "공연·전시": ("전시", "공연", "뮤지컬"),
    "음악": ("음악", "노래 추천", "플레이리스트"),
    "드라마": ("드라마", "드라마 추천", "넷플릭스 드라마"),
    "스타·연예인": ("연예인", "아이돌", "배우"),
    "만화·애니": ("애니", "만화", "웹툰"),
    "방송": ("방송", "예능", "시사 프로그램"),
    "일상·생각": ("일상", "생각 정리", "에세이"),
    "육아·결혼": ("육아", "결혼 준비", "신혼"),
    "반려동물": ("강아지", "고양이", "반려동물"),
    "좋은글·이미지": ("좋은 글", "감성 글귀", "배경화면"),
    "패션·미용": ("패션", "뷰티", "메이크업"),
    "인테리어·DIY": ("인테리어", "셀프 인테리어", "DIY"),
    "요리·레시피": ("요리", "레시피", "집밥"),
    "상품리뷰": ("리뷰", "사용기", "비교 리뷰"),
    "원예·재배": ("식물", "텃밭", "원예"),
    "게임": ("게임", "모바일 게임", "스팀 게임"),
    "스포츠": ("스포츠", "축구", "야구"),
    "사진": ("사진", "카메라", "사진 촬영"),
    "자동차": ("자동차", "전기차", "차량 리뷰"),
    "취미": ("취미", "캠핑", "수집"),
    "국내여행": ("국내 여행", "제주 여행", "벚꽃 여행"),
    "세계여행": ("해외 여행", "일본 여행", "동남아 여행"),
    "맛집": ("맛집", "카페", "메뉴"),
    "IT·컴퓨터": ("IT", "컴퓨터", "노트북"),
    "사회·정치": ("정치", "사회 이슈", "시사"),
    "건강·의학": ("건강", "영양제", "병원"),
    "비즈니스·경제": ("경제", "창업", "재테크"),
    "어학·외국어": ("영어 공부", "일본어", "중국어"),
    "교육·학문": ("교육", "공부법", "학문"),
}

CATEGORY_ALIASES: dict[str, str] = {
    "비즈니스경제": "비즈니스·경제",
    "패션미용": "패션·미용",
    "국내 여행": "국내여행",
    "해외여행": "세계여행",
    "세계 여행": "세계여행",
    "상품 리뷰": "상품리뷰",
    "it컴퓨터": "IT·컴퓨터",
    "it": "IT·컴퓨터",
    "사회정치": "사회·정치",
    "건강의학": "건강·의학",
    "어학외국어": "어학·외국어",
    "교육학문": "교육·학문",
    "미술디자인": "미술·디자인",
    "공연전시": "공연·전시",
    "스타연예인": "스타·연예인",
    "만화애니": "만화·애니",
    "일상생각": "일상·생각",
    "육아결혼": "육아·결혼",
    "좋은글이미지": "좋은글·이미지",
    "인테리어diy": "인테리어·DIY",
    "요리레시피": "요리·레시피",
    "원예재배": "원예·재배",
}

CATEGORY_SEARCH_AREAS: dict[str, str] = {
    "문학·책": "blog",
    "영화": "news",
    "미술·디자인": "blog",
    "공연·전시": "news",
    "음악": "news",
    "드라마": "news",
    "스타·연예인": "news",
    "만화·애니": "news",
    "방송": "news",
    "일상·생각": "blog",
    "육아·결혼": "blog",
    "반려동물": "blog",
    "좋은글·이미지": "blog",
    "패션·미용": "blog",
    "인테리어·DIY": "blog",
    "요리·레시피": "blog",
    "상품리뷰": "blog",
    "원예·재배": "blog",
    "게임": "news",
    "스포츠": "news",
    "사진": "blog",
    "자동차": "news",
    "취미": "blog",
    "국내여행": "blog",
    "세계여행": "blog",
    "맛집": "blog",
    "IT·컴퓨터": "news",
    "사회·정치": "news",
    "건강·의학": "blog",
    "비즈니스·경제": "news",
    "어학·외국어": "blog",
    "교육·학문": "news",
}

CATEGORY_TREND_TOPICS: dict[str, str] = {
    category: category
    for category in CATEGORY_CHOICES
}

DEFAULT_CATEGORY = "비즈니스·경제"
DEFAULT_CATEGORY_SOURCE = "naver_trend"
DEFAULT_TREND_SERVICE = "naver_blog"

CATEGORY_SOURCE_CHOICES = ("naver_trend", "preset_search")
TREND_SERVICE_CHOICES = ("naver_blog", "influencer")


def resolve_category_name(raw_category: str) -> str | None:
    normalized = normalize_category_key(raw_category)
    if not normalized:
        return None

    for category in CATEGORY_CHOICES:
        if normalize_category_key(category) == normalized:
            return category

    for alias, category in CATEGORY_ALIASES.items():
        if normalize_category_key(alias) == normalized:
            return category

    return None


def get_category_queries(category: str, include_all: bool) -> tuple[str, ...]:
    queries = CATEGORY_QUERIES.get(category, ())
    if include_all:
        return queries
    return queries[:1]


def get_category_search_area(category: str) -> str:
    return CATEGORY_SEARCH_AREAS.get(category, "blog")


def get_category_trend_topic(category: str) -> str | None:
    return CATEGORY_TREND_TOPICS.get(category)


def normalize_category_key(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z\u3131-\u318E\uAC00-\uD7A3]+", "", str(value or "")).lower()
