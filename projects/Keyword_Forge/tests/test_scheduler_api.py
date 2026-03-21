from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.scheduler.service import reset_job_scheduler_service_for_tests
from tests.test_scheduler_service import _fake_pipeline_runner


@pytest.fixture
def client(tmp_path: Path):
    reset_job_scheduler_service_for_tests(
        state_path=tmp_path / "scheduler_state.json",
        output_dir=tmp_path / "exports",
        runner=_fake_pipeline_runner,
        poll_interval_seconds=0.1,
    )
    with TestClient(app) as test_client:
        yield test_client


def _wait_for_job(client: TestClient, job_id: str, *, timeout_seconds: float = 5.0) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = client.get("/queue/snapshot")
        assert response.status_code == 200
        job = next(item for item in response.json()["queue"]["jobs"] if item["job_id"] == job_id)
        if job["status"] in {"completed", "partial", "failed", "blocked", "canceled"}:
            return job
        time.sleep(0.05)
    raise AssertionError("queue job did not finish in time")


def test_seed_batch_queue_endpoints_run_job_and_expose_artifact(client: TestClient) -> None:
    create_response = client.post(
        "/queue/jobs/seed-batch",
        json={
            "name": "시드 배치 테스트",
            "seed_keywords_text": "보험 추천\n대출 비교",
            "title_options": {"mode": "template"},
        },
    )

    assert create_response.status_code == 200
    queue_payload = create_response.json()["queue"]
    assert queue_payload["jobs"]

    job_id = queue_payload["jobs"][0]["job_id"]
    job = _wait_for_job(client, job_id)

    detail_response = client.get(f"/queue/jobs/{job_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["job"]["status"] == "completed"

    artifact_response = client.get(f"/queue/jobs/{job_id}/artifact")
    assert artifact_response.status_code == 200
    assert artifact_response.content[:2] == b"PK"


def test_daily_category_routine_endpoint_creates_routine(client: TestClient) -> None:
    response = client.post(
        "/queue/routines/daily-category",
        json={
            "name": "매일 카테고리 루틴",
            "categories": ["비즈니스·경제", "IT·컴퓨터"],
            "time_of_day": "06:30:00",
            "weekdays": [0, 1, 2, 3, 4, 5, 6],
            "title_options": {"mode": "template"},
        },
    )

    assert response.status_code == 200
    payload = response.json()["queue"]
    assert payload["routines"]
    assert payload["routines"][0]["name"] == "매일 카테고리 루틴"
