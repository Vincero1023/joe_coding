import sys
from pathlib import Path
from pprint import pprint

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.title.main import EXAMPLE_INPUT, run, title_module as title_generator_module


__all__ = ["run", "title_generator_module"]


if __name__ == "__main__":
    print("제목 생성 예시 결과")
    pprint(run({"selected_keywords": EXAMPLE_INPUT}), sort_dicts=False)
