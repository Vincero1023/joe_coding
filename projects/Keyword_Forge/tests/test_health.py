from pathlib import Path

from app.collector.main import run
from app.collector.service import CollectorService


sample_dir = Path(__file__).resolve().parents[1] / "app" / "collector" / "sample"


def test_collector_collects_keywords_from_requested_category() -> None:
    result = run(
        {
            "mode": "category",
            "category": "비즈니스경제",
            "seed_input": "",
            "options": {
                "collect_related": False,
                "collect_autocomplete": False,
                "collect_bulk": True,
            },
            "analysis_json_path": str(sample_dir / "site_analysis2.json"),
        }
    )

    keywords = result["collected_keywords"]
    assert keywords
    assert all(item["category"] == "비즈니스·경제" for item in keywords)
    assert all(set(item) == {"keyword", "category", "source", "raw"} for item in keywords[:10])
    assert all(item["source"] == "naver_trend" for item in keywords[:10])


def test_collector_seed_mode_returns_only_matching_keywords() -> None:
    service = CollectorService()
    seeded = service.run(
        {
            "mode": "seed",
            "category": "",
            "seed_input": "버터",
            "options": {
                "collect_related": True,
                "collect_autocomplete": True,
                "collect_bulk": False,
            },
            "analysis_json_path": str(sample_dir / "site_analysis2.json"),
        }
    )
    unfiltered = service.run(
        {
            "mode": "seed",
            "category": "",
            "seed_input": "",
            "options": {
                "collect_related": False,
                "collect_autocomplete": False,
                "collect_bulk": True,
            },
            "analysis_json_path": str(sample_dir / "site_analysis2.json"),
        }
    )

    assert seeded != unfiltered
    assert seeded["collected_keywords"]
    assert all("버터" in item["keyword"] for item in seeded["collected_keywords"])
    assert any(item["keyword"] == "버터떡" and item["category"] == "맛집" for item in seeded["collected_keywords"])


def test_collector_returns_empty_when_category_is_not_found() -> None:
    result = run(
        {
            "mode": "category",
            "category": "요리레시피",
            "seed_input": "",
            "options": {
                "collect_related": False,
                "collect_autocomplete": False,
                "collect_bulk": True,
            },
            "analysis_json_path": str(sample_dir / "site_analysis.json"),
        }
    )

    assert result == {"collected_keywords": []}
