import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.collector.service import CollectorService
from app.core.interfaces import ModuleRunner


service = CollectorService()

# 예시 입력: 카테고리 모드로 특정 주제의 키워드만 수집한다.
EXAMPLE_INPUT = {
    "mode": "category",
    "category": "비즈니스경제",
    "seed_input": "",
    "options": {
        "collect_related": False,
        "collect_autocomplete": False,
        "collect_bulk": True,
    },
    "analysis_json_path": "app/collector/sample/site_analysis2.json",
}

# 예시 출력: 실제 실행 시에는 collected_keywords 전체가 반환된다.
EXAMPLE_OUTPUT = {
    "collected_keywords": [
        {
            "keyword": "애착유형 테스트",
            "category": "비즈니스·경제",
            "source": "naver_trend",
            "raw": "애착유형 테스트",
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

