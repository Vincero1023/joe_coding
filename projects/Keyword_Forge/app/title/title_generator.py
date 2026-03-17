from __future__ import annotations

from typing import Any

from app.expander.utils.tokenizer import normalize_text
from app.title.category_detector import detect_category
from app.title.templates import build_blog_titles, build_naver_home_titles
from app.title.types import TitleOutputItem



def generate_titles(items: list[dict[str, Any]]) -> list[TitleOutputItem]:
    results: list[TitleOutputItem] = []

    for item in items:
        keyword = normalize_text(item.get("keyword"))
        if not keyword:
            continue

        category = detect_category(keyword)
        results.append(
            {
                "keyword": keyword,
                "titles": {
                    "naver_home": build_naver_home_titles(keyword, category),
                    "blog": build_blog_titles(keyword, category),
                },
            }
        )

    return results
