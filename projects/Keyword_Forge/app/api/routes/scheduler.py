from __future__ import annotations

import copy
from datetime import datetime, time as dt_time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.core.keyword_inputs import parse_keyword_text
from app.scheduler.service import (
    get_job_scheduler_service,
    parse_seed_keywords,
)


router = APIRouter()


class QueueEnvelope(BaseModel):
    queue: dict[str, Any] = Field(default_factory=dict)


class QueueJobEnvelope(BaseModel):
    job: dict[str, Any] = Field(default_factory=dict)


class QueuePauseRequest(BaseModel):
    reason: str = "manual_pause"


class SeedBatchQueueRequest(BaseModel):
    name: str = ""
    seed_keywords: list[str] = Field(default_factory=list)
    seed_keywords_text: str = ""
    category: str = ""
    category_source: str = ""
    collector_options: dict[str, Any] = Field(default_factory=dict)
    title_options: dict[str, Any] = Field(default_factory=dict)
    pipeline: dict[str, Any] = Field(default_factory=dict)
    scheduled_for: datetime | None = None


class DailyCategoryRoutineRequest(BaseModel):
    name: str = ""
    categories: list[str] = Field(default_factory=list)
    categories_text: str = ""
    time_of_day: dt_time = Field(default_factory=lambda: dt_time(hour=6, minute=0))
    weekdays: list[int] = Field(default_factory=lambda: list(range(7)))
    enabled: bool = True
    category_source: str = ""
    collector_options: dict[str, Any] = Field(default_factory=dict)
    title_options: dict[str, Any] = Field(default_factory=dict)
    pipeline: dict[str, Any] = Field(default_factory=dict)


@router.get("/queue/snapshot", response_model=QueueEnvelope)
def read_queue_snapshot() -> QueueEnvelope:
    service = get_job_scheduler_service()
    return QueueEnvelope(queue=service.get_snapshot())


@router.get("/queue/jobs/{job_id}", response_model=QueueJobEnvelope)
def read_queue_job(job_id: str) -> QueueJobEnvelope:
    service = get_job_scheduler_service()
    job = service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"message": "Queue job not found."})
    return QueueJobEnvelope(job=job)


@router.get("/queue/jobs/{job_id}/artifact")
def download_queue_job_artifact(job_id: str) -> FileResponse:
    service = get_job_scheduler_service()
    artifact_path = service.get_job_artifact_path(job_id)
    if artifact_path is None:
        raise HTTPException(status_code=404, detail={"message": "Queue artifact not found."})
    return FileResponse(path=artifact_path, filename=Path(artifact_path).name)


@router.post("/queue/jobs/seed-batch", response_model=QueueEnvelope)
def create_seed_batch_job(payload: SeedBatchQueueRequest) -> QueueEnvelope:
    service = get_job_scheduler_service()
    seeds = parse_seed_keywords(payload.seed_keywords, payload.seed_keywords_text)
    if not seeds:
        raise HTTPException(status_code=400, detail={"message": "At least one seed keyword is required."})

    base_input = _build_base_input(
        pipeline=payload.pipeline,
        category=payload.category,
        category_source=payload.category_source,
        collector_options=payload.collector_options,
        title_options=payload.title_options,
    )
    snapshot = service.enqueue_seed_batch_job(
        name=payload.name,
        seeds=seeds,
        base_input=base_input,
        scheduled_for=payload.scheduled_for,
    )
    return QueueEnvelope(queue=snapshot)


@router.post("/queue/jobs/{job_id}/cancel", response_model=QueueEnvelope)
def cancel_queue_job(job_id: str) -> QueueEnvelope:
    service = get_job_scheduler_service()
    try:
        snapshot = service.cancel_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"message": "Queue job not found."}) from exc
    return QueueEnvelope(queue=snapshot)


@router.post("/queue/runner/pause", response_model=QueueEnvelope)
def pause_queue_runner(payload: QueuePauseRequest) -> QueueEnvelope:
    service = get_job_scheduler_service()
    return QueueEnvelope(queue=service.pause(payload.reason))


@router.post("/queue/runner/resume", response_model=QueueEnvelope)
def resume_queue_runner() -> QueueEnvelope:
    service = get_job_scheduler_service()
    return QueueEnvelope(queue=service.resume())


@router.post("/queue/routines/daily-category", response_model=QueueEnvelope)
def create_daily_category_routine(payload: DailyCategoryRoutineRequest) -> QueueEnvelope:
    service = get_job_scheduler_service()
    categories = _parse_categories(payload.categories, payload.categories_text)
    if not categories:
        raise HTTPException(status_code=400, detail={"message": "At least one category is required."})

    base_input = _build_base_input(
        pipeline=payload.pipeline,
        category="",
        category_source=payload.category_source,
        collector_options=payload.collector_options,
        title_options=payload.title_options,
    )
    snapshot = service.create_daily_category_routine(
        name=payload.name,
        categories=categories,
        time_of_day=payload.time_of_day,
        weekdays=payload.weekdays,
        base_input=base_input,
        enabled=payload.enabled,
    )
    return QueueEnvelope(queue=snapshot)


@router.delete("/queue/routines/{routine_id}", response_model=QueueEnvelope)
def delete_daily_category_routine(routine_id: str) -> QueueEnvelope:
    service = get_job_scheduler_service()
    try:
        snapshot = service.delete_routine(routine_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"message": "Queue routine not found."}) from exc
    return QueueEnvelope(queue=snapshot)


def _build_base_input(
    *,
    pipeline: dict[str, Any],
    category: str,
    category_source: str,
    collector_options: dict[str, Any],
    title_options: dict[str, Any],
) -> dict[str, Any]:
    base_input = copy.deepcopy(pipeline if isinstance(pipeline, dict) else {})
    collector_payload = base_input.get("collector")
    if not isinstance(collector_payload, dict):
        collector_payload = {}
    base_input["collector"] = collector_payload

    if category.strip():
        collector_payload["category"] = category.strip()
    if category_source.strip():
        collector_payload["category_source"] = category_source.strip()
    if collector_options:
        collector_payload["options"] = _deep_merge_dicts(
            collector_payload.get("options") if isinstance(collector_payload.get("options"), dict) else {},
            collector_options,
        )

    if title_options:
        base_input["title_options"] = _deep_merge_dicts(
            base_input.get("title_options") if isinstance(base_input.get("title_options"), dict) else {},
            title_options,
        )

    return base_input


def _parse_categories(categories: list[str], categories_text: str) -> list[str]:
    values = [str(item or "").strip() for item in categories]
    values.extend(parse_keyword_text(categories_text))
    unique_values: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        unique_values.append(value)
    return unique_values


def _deep_merge_dicts(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(left)
    for key, value in right.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dicts(merged[key], value)
            continue
        merged[key] = copy.deepcopy(value)
    return merged
