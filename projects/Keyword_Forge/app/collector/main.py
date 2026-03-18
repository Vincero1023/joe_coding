import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.collector.categories import DEFAULT_CATEGORY
from app.collector.service import CollectorService
from app.core.interfaces import ModuleRunner


service = CollectorService()

EXAMPLE_INPUT = {
    "mode": "category",
    "category": DEFAULT_CATEGORY,
    "category_source": "preset_search",
    "seed_input": "",
    "options": {
        "collect_related": True,
        "collect_autocomplete": True,
        "collect_bulk": True,
    },
}

EXAMPLE_OUTPUT = {
    "collected_keywords": [
        {
            "keyword": "경제 뉴스",
            "category": DEFAULT_CATEGORY,
            "source": "naver_autocomplete",
            "raw": "경제",
        }
    ]
}


def run(input_data: dict) -> dict:
    return service.run(input_data)


class CollectorModule(ModuleRunner):
    def __init__(self, service: CollectorService) -> None:
        self._service = service

    def run(self, input_data: dict) -> dict:
        return self._service.run(input_data)


collector_module = CollectorModule(service=service)


if __name__ == "__main__":
    from pprint import pprint

    result = run(EXAMPLE_INPUT)
    preview = {"collected_keywords": result["collected_keywords"][:5]}

    print("카테고리 수집 예시 결과")
    print(f"요청 카테고리: {EXAMPLE_INPUT['category']}")
    print(f"수집 건수: {len(result['collected_keywords'])}")
    print("처음 5개만 표시합니다.")
    pprint(preview, sort_dicts=False)
