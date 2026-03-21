from __future__ import annotations

import copy
import json
import re
import threading
import traceback
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, time as dt_time, timedelta
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from openpyxl import Workbook

from app.core.keyword_inputs import parse_keyword_text
from app.core.runtime_settings import RuntimeGuardError, record_operation_start
from app.pipeline.main import pipeline_module


_KST = ZoneInfo("Asia/Seoul")
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_STATE_PATH = _PROJECT_ROOT / ".local" / "scheduler_state.json"
_DEFAULT_OUTPUT_DIR = _PROJECT_ROOT / "Status" / "queue_exports"
_DEFAULT_POLL_INTERVAL_SECONDS = 1.0
_SENSITIVE_KEY_PATTERN = re.compile(r"(api[_-]?key|secret|token|license|password)", re.IGNORECASE)

_JOB_STATUS_PENDING = "pending"
_JOB_STATUS_RUNNING = "running"
_JOB_STATUS_WAITING_RETRY = "waiting_retry"
_JOB_STATUS_COMPLETED = "completed"
_JOB_STATUS_PARTIAL = "partial"
_JOB_STATUS_FAILED = "failed"
_JOB_STATUS_BLOCKED = "blocked"
_JOB_STATUS_CANCELED = "canceled"

_ITEM_STATUS_PENDING = "pending"
_ITEM_STATUS_RUNNING = "running"
_ITEM_STATUS_COMPLETED = "completed"
_ITEM_STATUS_FAILED = "failed"
_ITEM_STATUS_BLOCKED = "blocked"
_ITEM_STATUS_CANCELED = "canceled"

_JOB_TYPE_SEED_BATCH = "seed_batch"
_JOB_TYPE_DAILY_CATEGORY = "daily_category"


PipelineRunner = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass
class QueueJobItemState:
    item_id: str
    value: str
    item_type: str
    status: str = _ITEM_STATUS_PENDING
    started_at: str = ""
    finished_at: str = ""
    duration_ms: int = 0
    attempt_count: int = 0
    result_counts: dict[str, int] = field(default_factory=dict)
    last_error: dict[str, Any] = field(default_factory=dict)


@dataclass
class QueueJobState:
    job_id: str
    job_type: str
    source: str
    name: str
    item_mode: str
    base_input: dict[str, Any] = field(default_factory=dict)
    items: list[QueueJobItemState] = field(default_factory=list)
    status: str = _JOB_STATUS_PENDING
    created_at: str = field(default_factory=lambda: _iso_now())
    updated_at: str = field(default_factory=lambda: _iso_now())
    scheduled_for: str = ""
    next_attempt_at: str = ""
    started_at: str = ""
    finished_at: str = ""
    artifact_path: str = ""
    origin_routine_id: str = ""
    cancel_requested: bool = False
    current_item_index: int = 0
    current_item_value: str = ""
    last_error: dict[str, Any] = field(default_factory=dict)


@dataclass
class DailyRoutineState:
    routine_id: str
    name: str
    categories: list[str]
    time_of_day: str
    weekdays: list[int]
    base_input: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    created_at: str = field(default_factory=lambda: _iso_now())
    updated_at: str = field(default_factory=lambda: _iso_now())
    next_run_at: str = ""
    last_enqueued_on: str = ""


@dataclass
class QueueRunnerState:
    running: bool = False
    paused: bool = False
    pause_reason: str = ""
    current_job_id: str = ""
    current_job_name: str = ""
    current_item_value: str = ""
    last_loop_error: str = ""
    updated_at: str = field(default_factory=lambda: _iso_now())


class JobSchedulerService:
    def __init__(
        self,
        *,
        state_path: Path | None = None,
        output_dir: Path | None = None,
        runner: PipelineRunner | None = None,
        poll_interval_seconds: float = _DEFAULT_POLL_INTERVAL_SECONDS,
    ) -> None:
        self._state_path = Path(state_path or _DEFAULT_STATE_PATH)
        self._output_dir = Path(output_dir or _DEFAULT_OUTPUT_DIR)
        self._runner = runner or pipeline_module.run
        self._poll_interval_seconds = max(0.2, float(poll_interval_seconds or _DEFAULT_POLL_INTERVAL_SECONDS))
        self._lock = threading.Lock()
        self._wake_event = threading.Event()
        self._stop_event = threading.Event()
        self._worker_thread: threading.Thread | None = None
        self._jobs: list[QueueJobState] = []
        self._routines: list[DailyRoutineState] = []
        self._runner_state = QueueRunnerState()
        self._load_state()

    def start(self) -> None:
        with self._lock:
            if self._worker_thread and self._worker_thread.is_alive():
                return
            self._stop_event.clear()
            self._worker_thread = threading.Thread(
                target=self._run_loop,
                name="keyword-forge-job-scheduler",
                daemon=True,
            )
            self._worker_thread.start()
            self._runner_state.updated_at = _iso_now()

    def shutdown(self) -> None:
        thread: threading.Thread | None = None
        with self._lock:
            thread = self._worker_thread
            self._worker_thread = None
            self._stop_event.set()
            self._wake_event.set()
        if thread and thread.is_alive():
            thread.join(timeout=5)
        with self._lock:
            self._runner_state.running = False
            self._runner_state.current_job_id = ""
            self._runner_state.current_job_name = ""
            self._runner_state.current_item_value = ""
            self._runner_state.updated_at = _iso_now()

    def pause(self, reason: str = "manual_pause") -> dict[str, Any]:
        with self._lock:
            self._runner_state.paused = True
            self._runner_state.pause_reason = str(reason or "").strip() or "manual_pause"
            self._runner_state.updated_at = _iso_now()
            self._persist_locked()
        return self.get_snapshot()

    def resume(self) -> dict[str, Any]:
        with self._lock:
            self._runner_state.paused = False
            self._runner_state.pause_reason = ""
            self._runner_state.updated_at = _iso_now()
            self._persist_locked()
        self._wake_event.set()
        return self.get_snapshot()

    def get_snapshot(self) -> dict[str, Any]:
        with self._lock:
            return self._build_snapshot_locked()

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._find_job_locked(job_id)
            if job is None:
                return None
            return _serialize_job(job)

    def get_job_artifact_path(self, job_id: str) -> Path | None:
        with self._lock:
            job = self._find_job_locked(job_id)
            if job is None or not job.artifact_path:
                return None
            artifact_path = Path(job.artifact_path)
        return artifact_path if artifact_path.exists() else None

    def enqueue_seed_batch_job(
        self,
        *,
        name: str,
        seeds: list[str],
        base_input: dict[str, Any] | None = None,
        scheduled_for: datetime | None = None,
    ) -> dict[str, Any]:
        normalized_seeds = _unique_strings(seeds)
        if not normalized_seeds:
            raise ValueError("최소 1개의 시드 키워드가 필요합니다.")

        job = QueueJobState(
            job_id=_new_id("job"),
            job_type=_JOB_TYPE_SEED_BATCH,
            source="manual",
            name=(str(name or "").strip() or f"시드 배치 {len(normalized_seeds)}건"),
            item_mode="seed",
            base_input=_clean_base_input(base_input),
            scheduled_for=_format_local_datetime(scheduled_for) if scheduled_for else "",
            items=[
                QueueJobItemState(
                    item_id=_new_id("item"),
                    value=seed,
                    item_type="seed",
                )
                for seed in normalized_seeds
            ],
        )

        with self._lock:
            self._jobs.append(job)
            self._persist_locked()
            snapshot = self._build_snapshot_locked()
        self.start()
        self._wake_event.set()
        return snapshot

    def create_daily_category_routine(
        self,
        *,
        name: str,
        categories: list[str],
        time_of_day: dt_time,
        weekdays: list[int] | None,
        base_input: dict[str, Any] | None = None,
        enabled: bool = True,
        reference_now: datetime | None = None,
    ) -> dict[str, Any]:
        normalized_categories = _unique_strings(categories)
        if not normalized_categories:
            raise ValueError("최소 1개의 카테고리가 필요합니다.")

        normalized_weekdays = _normalize_weekdays(weekdays)
        routine = DailyRoutineState(
            routine_id=_new_id("routine"),
            name=(str(name or "").strip() or f"일일 카테고리 루틴 {len(normalized_categories)}건"),
            categories=normalized_categories,
            time_of_day=time_of_day.strftime("%H:%M"),
            weekdays=normalized_weekdays,
            base_input=_clean_base_input(base_input),
            enabled=bool(enabled),
        )
        now = _ensure_kst_datetime(reference_now)
        routine.next_run_at = _format_local_datetime(
            _compute_next_run_datetime(
                time_of_day=time_of_day,
                weekdays=normalized_weekdays,
                reference_now=now,
            )
        )

        with self._lock:
            self._routines.append(routine)
            self._persist_locked()
            snapshot = self._build_snapshot_locked()
        self.start()
        self._wake_event.set()
        return snapshot

    def delete_routine(self, routine_id: str) -> dict[str, Any]:
        with self._lock:
            initial_size = len(self._routines)
            self._routines = [routine for routine in self._routines if routine.routine_id != routine_id]
            if len(self._routines) == initial_size:
                raise KeyError(routine_id)
            self._persist_locked()
            return self._build_snapshot_locked()

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            job = self._find_job_locked(job_id)
            if job is None:
                raise KeyError(job_id)

            if job.status in {_JOB_STATUS_COMPLETED, _JOB_STATUS_PARTIAL, _JOB_STATUS_FAILED, _JOB_STATUS_CANCELED}:
                return self._build_snapshot_locked()

            if job.status == _JOB_STATUS_RUNNING:
                job.cancel_requested = True
            else:
                job.status = _JOB_STATUS_CANCELED
                job.finished_at = _iso_now()
                job.updated_at = _iso_now()
                for item in job.items:
                    if item.status == _ITEM_STATUS_PENDING:
                        item.status = _ITEM_STATUS_CANCELED
            self._persist_locked()
            return self._build_snapshot_locked()

    def queue_due_routines(self, now: datetime | None = None) -> int:
        current_time = _ensure_kst_datetime(now)
        with self._lock:
            created_count = self._queue_due_routines_locked(current_time)
        if created_count:
            self.start()
            self._wake_event.set()
        return created_count

    def process_pending_jobs_once(self) -> bool:
        self.queue_due_routines()
        claimed_job = self._claim_next_job()
        if claimed_job is None:
            return False

        self._execute_job(claimed_job)
        return True

    def reset_for_tests(self) -> None:
        self.shutdown()
        with self._lock:
            self._jobs = []
            self._routines = []
            self._runner_state = QueueRunnerState()
            if self._state_path.exists():
                self._state_path.unlink()

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                processed = self.process_pending_jobs_once()
            except Exception:
                with self._lock:
                    self._runner_state.running = False
                    self._runner_state.last_loop_error = "".join(traceback.format_exc(limit=5))
                    self._runner_state.updated_at = _iso_now()
                    self._persist_locked()
                processed = False

            timeout = 0.2 if processed else self._poll_interval_seconds
            self._wake_event.wait(timeout=timeout)
            self._wake_event.clear()

    def _claim_next_job(self) -> QueueJobState | None:
        with self._lock:
            if self._runner_state.paused or self._runner_state.current_job_id:
                return None

            now = _now_kst()
            job = next(
                (
                    candidate
                    for candidate in sorted(self._jobs, key=_job_sort_key)
                    if _job_is_runnable(candidate, now)
                ),
                None,
            )
            if job is None:
                return None

            job.status = _JOB_STATUS_RUNNING
            job.started_at = job.started_at or _iso_now()
            job.updated_at = _iso_now()
            job.current_item_index = 0
            job.current_item_value = ""
            self._runner_state.running = True
            self._runner_state.current_job_id = job.job_id
            self._runner_state.current_job_name = job.name
            self._runner_state.current_item_value = ""
            self._runner_state.updated_at = _iso_now()
            self._persist_locked()
            return copy.deepcopy(job)

    def _execute_job(self, claimed_job: QueueJobState) -> None:
        item_results: list[dict[str, Any]] = []
        try:
            for item_index, item in enumerate(claimed_job.items, start=1):
                live_item = self._get_live_item(claimed_job.job_id, item.item_id)
                if live_item is None or live_item.status == _ITEM_STATUS_COMPLETED:
                    continue

                if self._job_cancel_requested(claimed_job.job_id):
                    self._cancel_remaining_items(claimed_job.job_id)
                    break

                self._mark_item_running(claimed_job.job_id, live_item.item_id, item_index)
                pipeline_input = self._build_pipeline_input(claimed_job, live_item)
                started_at = datetime.now()

                try:
                    record_operation_start(f"queue:{claimed_job.job_type}")
                    result = self._runner(pipeline_input)
                except RuntimeGuardError as exc:
                    self._handle_runtime_guard(claimed_job.job_id, live_item.item_id, exc)
                    return
                except Exception as exc:
                    self._mark_item_failed(
                        claimed_job.job_id,
                        live_item.item_id,
                        exc,
                        started_at=started_at,
                    )
                    continue

                item_results.append(
                    {
                        "item_id": live_item.item_id,
                        "item_value": live_item.value,
                        "item_type": live_item.item_type,
                        "result": result if isinstance(result, dict) else {},
                    }
                )
                self._mark_item_completed(
                    claimed_job.job_id,
                    live_item.item_id,
                    started_at=started_at,
                    result_counts=_build_result_counts(result if isinstance(result, dict) else {}),
                )

            self._finalize_job(claimed_job.job_id, item_results)
        finally:
            with self._lock:
                self._runner_state.running = False
                self._runner_state.current_job_id = ""
                self._runner_state.current_job_name = ""
                self._runner_state.current_item_value = ""
                self._runner_state.updated_at = _iso_now()
                self._persist_locked()

    def _finalize_job(self, job_id: str, item_results: list[dict[str, Any]]) -> None:
        artifact_path = self._write_job_workbook(job_id, item_results)
        with self._lock:
            job = self._find_job_locked(job_id)
            if job is None:
                return

            completed_count = sum(1 for item in job.items if item.status == _ITEM_STATUS_COMPLETED)
            failed_count = sum(1 for item in job.items if item.status == _ITEM_STATUS_FAILED)
            blocked_count = sum(1 for item in job.items if item.status == _ITEM_STATUS_BLOCKED)
            canceled_count = sum(1 for item in job.items if item.status == _ITEM_STATUS_CANCELED)

            if job.status not in {_JOB_STATUS_WAITING_RETRY, _JOB_STATUS_BLOCKED}:
                if completed_count == len(job.items):
                    job.status = _JOB_STATUS_COMPLETED
                elif completed_count > 0 and (failed_count or canceled_count):
                    job.status = _JOB_STATUS_PARTIAL
                elif failed_count and completed_count == 0:
                    job.status = _JOB_STATUS_FAILED
                elif canceled_count and completed_count == 0 and failed_count == 0:
                    job.status = _JOB_STATUS_CANCELED
                elif blocked_count:
                    job.status = _JOB_STATUS_BLOCKED
                else:
                    job.status = _JOB_STATUS_PARTIAL if completed_count else _JOB_STATUS_FAILED

            job.current_item_index = 0
            job.current_item_value = ""
            job.finished_at = _iso_now()
            job.updated_at = _iso_now()
            if artifact_path is not None:
                job.artifact_path = str(artifact_path)
            self._persist_locked()

    def _handle_runtime_guard(self, job_id: str, item_id: str, exc: RuntimeGuardError) -> None:
        retry_at = _resolve_retry_datetime(exc)
        with self._lock:
            job = self._find_job_locked(job_id)
            item = self._find_item_locked(job, item_id) if job is not None else None
            if job is None or item is None:
                return

            item.status = _ITEM_STATUS_PENDING if retry_at else _ITEM_STATUS_BLOCKED
            item.last_error = _normalize_exception_payload(exc)
            job.last_error = _normalize_exception_payload(exc)
            job.updated_at = _iso_now()

            if retry_at is not None:
                job.status = _JOB_STATUS_WAITING_RETRY
                job.next_attempt_at = _format_local_datetime(retry_at)
            else:
                job.status = _JOB_STATUS_BLOCKED
                self._runner_state.paused = True
                self._runner_state.pause_reason = str(exc) or getattr(exc, "code", "runtime_guard")

            self._persist_locked()

    def _mark_item_running(self, job_id: str, item_id: str, item_index: int) -> None:
        with self._lock:
            job = self._find_job_locked(job_id)
            item = self._find_item_locked(job, item_id) if job is not None else None
            if job is None or item is None:
                return
            item.status = _ITEM_STATUS_RUNNING
            item.started_at = _iso_now()
            item.finished_at = ""
            item.attempt_count += 1
            job.current_item_index = item_index
            job.current_item_value = item.value
            job.updated_at = _iso_now()
            self._runner_state.current_item_value = item.value
            self._runner_state.updated_at = _iso_now()
            self._persist_locked()

    def _mark_item_completed(
        self,
        job_id: str,
        item_id: str,
        *,
        started_at: datetime,
        result_counts: dict[str, int],
    ) -> None:
        with self._lock:
            job = self._find_job_locked(job_id)
            item = self._find_item_locked(job, item_id) if job is not None else None
            if job is None or item is None:
                return
            item.status = _ITEM_STATUS_COMPLETED
            item.finished_at = _iso_now()
            item.duration_ms = int((datetime.now() - started_at).total_seconds() * 1000)
            item.result_counts = result_counts
            item.last_error = {}
            job.updated_at = _iso_now()
            self._persist_locked()

    def _mark_item_failed(
        self,
        job_id: str,
        item_id: str,
        exc: Exception,
        *,
        started_at: datetime,
    ) -> None:
        with self._lock:
            job = self._find_job_locked(job_id)
            item = self._find_item_locked(job, item_id) if job is not None else None
            if job is None or item is None:
                return
            item.status = _ITEM_STATUS_FAILED
            item.finished_at = _iso_now()
            item.duration_ms = int((datetime.now() - started_at).total_seconds() * 1000)
            item.last_error = _normalize_exception_payload(exc)
            job.last_error = item.last_error
            job.updated_at = _iso_now()
            self._persist_locked()

    def _cancel_remaining_items(self, job_id: str) -> None:
        with self._lock:
            job = self._find_job_locked(job_id)
            if job is None:
                return
            for item in job.items:
                if item.status == _ITEM_STATUS_PENDING:
                    item.status = _ITEM_STATUS_CANCELED
            job.status = _JOB_STATUS_CANCELED
            job.updated_at = _iso_now()
            self._persist_locked()

    def _job_cancel_requested(self, job_id: str) -> bool:
        with self._lock:
            job = self._find_job_locked(job_id)
            return bool(job.cancel_requested) if job is not None else False

    def _build_pipeline_input(self, job: QueueJobState, item: QueueJobItemState) -> dict[str, Any]:
        payload = copy.deepcopy(job.base_input)
        collector_payload = payload.get("collector")
        if not isinstance(collector_payload, dict):
            collector_payload = {}
        payload["collector"] = collector_payload

        if job.item_mode == "seed":
            collector_payload["mode"] = "seed"
            collector_payload["seed_input"] = item.value
        else:
            collector_payload["mode"] = "category"
            collector_payload["category"] = item.value
            collector_payload.setdefault("seed_input", "")

        return payload

    def _queue_due_routines_locked(self, now: datetime) -> int:
        created_count = 0
        for routine in self._routines:
            if not routine.enabled or not routine.next_run_at:
                continue
            next_run = _parse_local_datetime(routine.next_run_at)
            if next_run is None or next_run > now:
                continue

            day_key = now.date().isoformat()
            if routine.last_enqueued_on == day_key:
                routine.next_run_at = _format_local_datetime(
                    _compute_next_run_datetime(
                        time_of_day=_parse_time_of_day(routine.time_of_day),
                        weekdays=routine.weekdays,
                        reference_now=now + timedelta(minutes=1),
                    )
                )
                routine.updated_at = _iso_now()
                continue

            job = QueueJobState(
                job_id=_new_id("job"),
                job_type=_JOB_TYPE_DAILY_CATEGORY,
                source="routine",
                name=routine.name,
                item_mode="category",
                base_input=_clean_base_input(routine.base_input),
                scheduled_for=routine.next_run_at,
                origin_routine_id=routine.routine_id,
                items=[
                    QueueJobItemState(
                        item_id=_new_id("item"),
                        value=category,
                        item_type="category",
                    )
                    for category in routine.categories
                ],
            )
            self._jobs.append(job)
            created_count += 1
            routine.last_enqueued_on = day_key
            routine.next_run_at = _format_local_datetime(
                _compute_next_run_datetime(
                    time_of_day=_parse_time_of_day(routine.time_of_day),
                    weekdays=routine.weekdays,
                    reference_now=now + timedelta(minutes=1),
                )
            )
            routine.updated_at = _iso_now()

        if created_count:
            self._persist_locked()
        return created_count

    def _write_job_workbook(self, job_id: str, item_results: list[dict[str, Any]]) -> Path | None:
        with self._lock:
            job = self._find_job_locked(job_id)
            if job is None:
                return None
            job_snapshot = copy.deepcopy(job)

        workbook = Workbook()
        default_sheet = workbook.active
        workbook.remove(default_sheet)

        summary_rows = _build_summary_rows(job_snapshot)
        error_rows = _build_error_rows(job_snapshot)
        _append_table_sheet(workbook, "summary", summary_rows)

        collected_rows: list[dict[str, Any]] = []
        expanded_rows: list[dict[str, Any]] = []
        analyzed_rows: list[dict[str, Any]] = []
        selected_rows: list[dict[str, Any]] = []
        longtail_rows: list[dict[str, Any]] = []
        title_rows: list[dict[str, Any]] = []

        for item_result in item_results:
            item_id = str(item_result.get("item_id") or "")
            item_value = str(item_result.get("item_value") or "")
            result = item_result.get("result") if isinstance(item_result.get("result"), dict) else {}
            context = {
                "job_id": job_snapshot.job_id,
                "job_name": job_snapshot.name,
                "job_type": job_snapshot.job_type,
                "item_id": item_id,
                "item_value": item_value,
            }
            collected_rows.extend(_normalize_payload_rows(result.get("collected_keywords"), context))
            expanded_rows.extend(_normalize_payload_rows(result.get("expanded_keywords"), context))
            analyzed_rows.extend(_normalize_payload_rows(result.get("analyzed_keywords"), context))
            selected_rows.extend(_normalize_payload_rows(result.get("selected_keywords"), context))
            longtail_rows.extend(_normalize_payload_rows(result.get("longtail_suggestions"), context))
            title_rows.extend(_normalize_title_rows(result.get("generated_titles"), context))

        _append_table_sheet(workbook, "collected", collected_rows)
        _append_table_sheet(workbook, "expanded", expanded_rows)
        _append_table_sheet(workbook, "analyzed", analyzed_rows)
        _append_table_sheet(workbook, "selected", selected_rows)
        _append_table_sheet(workbook, "longtail", longtail_rows)
        _append_table_sheet(workbook, "titles", title_rows)
        _append_table_sheet(workbook, "errors", error_rows)

        timestamp = _now_kst().strftime("%Y%m%d-%H%M%S")
        output_dir = self._output_dir / _now_kst().strftime("%Y-%m-%d")
        output_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = output_dir / f"queue-{timestamp}-{job_snapshot.job_id}.xlsx"
        workbook.save(artifact_path)
        return artifact_path

    def _get_live_item(self, job_id: str, item_id: str) -> QueueJobItemState | None:
        with self._lock:
            job = self._find_job_locked(job_id)
            item = self._find_item_locked(job, item_id) if job is not None else None
            if item is None:
                return None
            return copy.deepcopy(item)

    def _find_job_locked(self, job_id: str) -> QueueJobState | None:
        return next((job for job in self._jobs if job.job_id == job_id), None)

    def _find_item_locked(self, job: QueueJobState | None, item_id: str) -> QueueJobItemState | None:
        if job is None:
            return None
        return next((item for item in job.items if item.item_id == item_id), None)

    def _build_snapshot_locked(self) -> dict[str, Any]:
        return {
            "runner": asdict(self._runner_state),
            "jobs": [_serialize_job(job) for job in sorted(self._jobs, key=_job_sort_key)],
            "routines": [_serialize_routine(routine) for routine in sorted(self._routines, key=_routine_sort_key)],
            "paths": {
                "state_path": str(self._state_path),
                "output_dir": str(self._output_dir),
            },
        }

    def _load_state(self) -> None:
        with self._lock:
            if not self._state_path.exists():
                return
            try:
                raw = json.loads(self._state_path.read_text(encoding="utf-8"))
            except Exception:
                self._jobs = []
                self._routines = []
                self._runner_state = QueueRunnerState()
                return

            self._jobs = [_deserialize_job(item) for item in raw.get("jobs", []) if isinstance(item, dict)]
            self._routines = [
                _deserialize_routine(item)
                for item in raw.get("routines", [])
                if isinstance(item, dict)
            ]
            runner = raw.get("runner")
            self._runner_state = _deserialize_runner_state(runner if isinstance(runner, dict) else {})

            for job in self._jobs:
                if job.status == _JOB_STATUS_RUNNING:
                    job.status = _JOB_STATUS_PENDING
                    job.current_item_index = 0
                    job.current_item_value = ""
                for item in job.items:
                    if item.status == _ITEM_STATUS_RUNNING:
                        item.status = _ITEM_STATUS_PENDING

            self._runner_state.running = False
            self._runner_state.current_job_id = ""
            self._runner_state.current_job_name = ""
            self._runner_state.current_item_value = ""
            self._runner_state.updated_at = _iso_now()

    def _persist_locked(self) -> None:
        payload = {
            "jobs": [asdict(job) for job in self._jobs],
            "routines": [asdict(routine) for routine in self._routines],
            "runner": asdict(self._runner_state),
        }
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self._state_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(self._state_path)


def _serialize_job(job: QueueJobState) -> dict[str, Any]:
    completed_count = sum(1 for item in job.items if item.status == _ITEM_STATUS_COMPLETED)
    failed_count = sum(1 for item in job.items if item.status == _ITEM_STATUS_FAILED)
    blocked_count = sum(1 for item in job.items if item.status == _ITEM_STATUS_BLOCKED)
    canceled_count = sum(1 for item in job.items if item.status == _ITEM_STATUS_CANCELED)
    pending_count = sum(1 for item in job.items if item.status == _ITEM_STATUS_PENDING)
    return {
        "job_id": job.job_id,
        "job_type": job.job_type,
        "source": job.source,
        "name": job.name,
        "item_mode": job.item_mode,
        "status": job.status,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "scheduled_for": job.scheduled_for,
        "next_attempt_at": job.next_attempt_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "artifact_path": job.artifact_path,
        "origin_routine_id": job.origin_routine_id,
        "cancel_requested": job.cancel_requested,
        "current_item_index": job.current_item_index,
        "current_item_value": job.current_item_value,
        "last_error": job.last_error,
        "item_count": len(job.items),
        "completed_count": completed_count,
        "failed_count": failed_count,
        "blocked_count": blocked_count,
        "canceled_count": canceled_count,
        "pending_count": pending_count,
        "items": [
            {
                "item_id": item.item_id,
                "value": item.value,
                "item_type": item.item_type,
                "status": item.status,
                "started_at": item.started_at,
                "finished_at": item.finished_at,
                "duration_ms": item.duration_ms,
                "attempt_count": item.attempt_count,
                "result_counts": item.result_counts,
                "last_error": item.last_error,
            }
            for item in job.items
        ],
        "input_summary": _summarize_input_payload(job.base_input),
    }


def _serialize_routine(routine: DailyRoutineState) -> dict[str, Any]:
    return {
        "routine_id": routine.routine_id,
        "name": routine.name,
        "categories": list(routine.categories),
        "time_of_day": routine.time_of_day,
        "weekdays": list(routine.weekdays),
        "enabled": routine.enabled,
        "created_at": routine.created_at,
        "updated_at": routine.updated_at,
        "next_run_at": routine.next_run_at,
        "last_enqueued_on": routine.last_enqueued_on,
        "input_summary": _summarize_input_payload(routine.base_input),
    }


def _deserialize_job(raw: dict[str, Any]) -> QueueJobState:
    return QueueJobState(
        job_id=str(raw.get("job_id") or _new_id("job")),
        job_type=str(raw.get("job_type") or _JOB_TYPE_SEED_BATCH),
        source=str(raw.get("source") or "manual"),
        name=str(raw.get("name") or "Queue Job"),
        item_mode=str(raw.get("item_mode") or "seed"),
        base_input=raw.get("base_input") if isinstance(raw.get("base_input"), dict) else {},
        items=[
            QueueJobItemState(
                item_id=str(item.get("item_id") or _new_id("item")),
                value=str(item.get("value") or ""),
                item_type=str(item.get("item_type") or "seed"),
                status=str(item.get("status") or _ITEM_STATUS_PENDING),
                started_at=str(item.get("started_at") or ""),
                finished_at=str(item.get("finished_at") or ""),
                duration_ms=int(item.get("duration_ms") or 0),
                attempt_count=int(item.get("attempt_count") or 0),
                result_counts=item.get("result_counts") if isinstance(item.get("result_counts"), dict) else {},
                last_error=item.get("last_error") if isinstance(item.get("last_error"), dict) else {},
            )
            for item in raw.get("items", [])
            if isinstance(item, dict)
        ],
        status=str(raw.get("status") or _JOB_STATUS_PENDING),
        created_at=str(raw.get("created_at") or _iso_now()),
        updated_at=str(raw.get("updated_at") or _iso_now()),
        scheduled_for=str(raw.get("scheduled_for") or ""),
        next_attempt_at=str(raw.get("next_attempt_at") or ""),
        started_at=str(raw.get("started_at") or ""),
        finished_at=str(raw.get("finished_at") or ""),
        artifact_path=str(raw.get("artifact_path") or ""),
        origin_routine_id=str(raw.get("origin_routine_id") or ""),
        cancel_requested=bool(raw.get("cancel_requested")),
        current_item_index=int(raw.get("current_item_index") or 0),
        current_item_value=str(raw.get("current_item_value") or ""),
        last_error=raw.get("last_error") if isinstance(raw.get("last_error"), dict) else {},
    )


def _deserialize_routine(raw: dict[str, Any]) -> DailyRoutineState:
    return DailyRoutineState(
        routine_id=str(raw.get("routine_id") or _new_id("routine")),
        name=str(raw.get("name") or "Daily Routine"),
        categories=[str(item) for item in raw.get("categories", []) if str(item or "").strip()],
        time_of_day=str(raw.get("time_of_day") or "06:00"),
        weekdays=_normalize_weekdays(raw.get("weekdays")),
        base_input=raw.get("base_input") if isinstance(raw.get("base_input"), dict) else {},
        enabled=bool(raw.get("enabled", True)),
        created_at=str(raw.get("created_at") or _iso_now()),
        updated_at=str(raw.get("updated_at") or _iso_now()),
        next_run_at=str(raw.get("next_run_at") or ""),
        last_enqueued_on=str(raw.get("last_enqueued_on") or ""),
    )


def _deserialize_runner_state(raw: dict[str, Any]) -> QueueRunnerState:
    return QueueRunnerState(
        running=bool(raw.get("running")),
        paused=bool(raw.get("paused")),
        pause_reason=str(raw.get("pause_reason") or ""),
        current_job_id=str(raw.get("current_job_id") or ""),
        current_job_name=str(raw.get("current_job_name") or ""),
        current_item_value=str(raw.get("current_item_value") or ""),
        last_loop_error=str(raw.get("last_loop_error") or ""),
        updated_at=str(raw.get("updated_at") or _iso_now()),
    )


def _append_table_sheet(workbook: Workbook, sheet_name: str, rows: list[dict[str, Any]]) -> None:
    worksheet = workbook.create_sheet(title=sheet_name[:31] or "sheet")
    if not rows:
        worksheet.append(["status"])
        worksheet.append(["empty"])
        return

    headers = sorted({key for row in rows for key in row.keys()})
    worksheet.append(headers)
    for row in rows:
        worksheet.append([row.get(header, "") for header in headers])


def _build_summary_rows(job: QueueJobState) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(job.items, start=1):
        row = {
            "job_id": job.job_id,
            "job_name": job.name,
            "job_type": job.job_type,
            "job_status": job.status,
            "item_index": index,
            "item_id": item.item_id,
            "item_value": item.value,
            "item_type": item.item_type,
            "item_status": item.status,
            "attempt_count": item.attempt_count,
            "duration_ms": item.duration_ms,
            "started_at": item.started_at,
            "finished_at": item.finished_at,
        }
        row.update({f"count_{key}": value for key, value in sorted(item.result_counts.items())})
        if item.last_error:
            row["last_error"] = _safe_json(item.last_error)
        rows.append(row)
    return rows


def _build_error_rows(job: QueueJobState) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in job.items:
        if not item.last_error:
            continue
        rows.append(
            {
                "job_id": job.job_id,
                "job_name": job.name,
                "item_id": item.item_id,
                "item_value": item.value,
                "item_status": item.status,
                "error_type": item.last_error.get("type", ""),
                "error_code": item.last_error.get("code", ""),
                "message": item.last_error.get("message", ""),
                "detail": _safe_json(item.last_error.get("detail")),
            }
        )
    if job.last_error and not rows:
        rows.append(
            {
                "job_id": job.job_id,
                "job_name": job.name,
                "item_id": "",
                "item_value": "",
                "item_status": job.status,
                "error_type": job.last_error.get("type", ""),
                "error_code": job.last_error.get("code", ""),
                "message": job.last_error.get("message", ""),
                "detail": _safe_json(job.last_error.get("detail")),
            }
        )
    return rows


def _normalize_payload_rows(payload: Any, context: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        row = dict(context)
        row.update(_flatten_row(item))
        rows.append(row)
    return rows


def _normalize_title_rows(payload: Any, context: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        titles = item.get("titles") if isinstance(item.get("titles"), dict) else {}
        naver_home = titles.get("naver_home") if isinstance(titles.get("naver_home"), list) else []
        blog = titles.get("blog") if isinstance(titles.get("blog"), list) else []
        quality_report = item.get("quality_report") if isinstance(item.get("quality_report"), dict) else {}
        row = dict(context)
        row.update(
            {
                "keyword": item.get("keyword", ""),
                "target_mode": item.get("target_mode", ""),
                "source_kind": item.get("source_kind", ""),
                "naver_home_1": naver_home[0] if len(naver_home) > 0 else "",
                "naver_home_2": naver_home[1] if len(naver_home) > 1 else "",
                "blog_1": blog[0] if len(blog) > 0 else "",
                "blog_2": blog[1] if len(blog) > 1 else "",
                "quality_label": quality_report.get("label", ""),
                "quality_score": quality_report.get("bundle_score", ""),
            }
        )
        rows.append(row)
    return rows


def _flatten_row(item: dict[str, Any]) -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    for key, value in item.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            flattened[key] = value
        else:
            flattened[key] = _safe_json(value)
    return flattened


def _build_result_counts(result: dict[str, Any]) -> dict[str, int]:
    keys = (
        "collected_keywords",
        "expanded_keywords",
        "analyzed_keywords",
        "selected_keywords",
        "longtail_suggestions",
        "generated_titles",
    )
    return {
        key: len(result.get(key, []))
        for key in keys
        if isinstance(result.get(key), list)
    }


def _normalize_exception_payload(exc: Exception) -> dict[str, Any]:
    payload = {
        "type": exc.__class__.__name__,
        "message": str(exc).strip() or exc.__class__.__name__,
    }
    if isinstance(exc, RuntimeGuardError):
        payload["code"] = getattr(exc, "code", "runtime_guard")
        payload["detail"] = getattr(exc, "detail", {})
        payload["status_code"] = getattr(exc, "status_code", 429)
    return payload


def _resolve_retry_datetime(exc: RuntimeGuardError) -> datetime | None:
    code = str(getattr(exc, "code", "") or "").strip()
    now = _now_kst()
    if code in {"daily_operation_limit_reached", "daily_naver_request_limit_reached"}:
        tomorrow = now.date() + timedelta(days=1)
        return datetime.combine(tomorrow, dt_time(hour=0, minute=5), tzinfo=_KST)
    if code == "continuous_runtime_limit_reached":
        return now + timedelta(minutes=30)
    return None


def _job_is_runnable(job: QueueJobState, now: datetime) -> bool:
    if job.cancel_requested and job.status != _JOB_STATUS_RUNNING:
        return False
    if job.status == _JOB_STATUS_PENDING:
        if job.scheduled_for:
            scheduled_for = _parse_local_datetime(job.scheduled_for)
            return scheduled_for is None or scheduled_for <= now
        return True
    if job.status == _JOB_STATUS_WAITING_RETRY:
        retry_at = _parse_local_datetime(job.next_attempt_at)
        return retry_at is None or retry_at <= now
    return False


def _job_sort_key(job: QueueJobState) -> tuple[str, str, str]:
    due_key = job.next_attempt_at or job.scheduled_for or job.created_at
    return (due_key, job.created_at, job.job_id)


def _routine_sort_key(routine: DailyRoutineState) -> tuple[str, str]:
    return (routine.next_run_at or "9999-12-31T23:59:59+09:00", routine.routine_id)


def _clean_base_input(value: Any) -> dict[str, Any]:
    return copy.deepcopy(value) if isinstance(value, dict) else {}


def _summarize_input_payload(payload: dict[str, Any]) -> dict[str, Any]:
    collector = payload.get("collector") if isinstance(payload.get("collector"), dict) else {}
    expander = payload.get("expander") if isinstance(payload.get("expander"), dict) else {}
    title_options = payload.get("title_options") if isinstance(payload.get("title_options"), dict) else {}
    return {
        "collector_keys": sorted(collector.keys()),
        "expander_keys": sorted(expander.keys()),
        "title_mode": title_options.get("mode", ""),
        "title_provider": title_options.get("provider", ""),
        "has_sensitive_overrides": _contains_sensitive_keys(payload),
    }


def _contains_sensitive_keys(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if _SENSITIVE_KEY_PATTERN.search(str(key or "")):
                if str(item or "").strip():
                    return True
            if _contains_sensitive_keys(item):
                return True
    if isinstance(value, list):
        return any(_contains_sensitive_keys(item) for item in value)
    return False


def _normalize_weekdays(value: Any) -> list[int]:
    if not isinstance(value, list) or not value:
        return list(range(7))
    weekdays = sorted({int(item) for item in value if str(item).strip().isdigit() and 0 <= int(item) <= 6})
    return weekdays or list(range(7))


def _parse_time_of_day(value: str) -> dt_time:
    hour_text, _, minute_text = str(value or "06:00").partition(":")
    hour = max(0, min(23, int(hour_text or 6)))
    minute = max(0, min(59, int(minute_text or 0)))
    return dt_time(hour=hour, minute=minute)


def _compute_next_run_datetime(
    *,
    time_of_day: dt_time,
    weekdays: list[int],
    reference_now: datetime,
) -> datetime:
    current = _ensure_kst_datetime(reference_now)
    for offset in range(8):
        candidate_date = current.date() + timedelta(days=offset)
        if candidate_date.weekday() not in weekdays:
            continue
        candidate_dt = datetime.combine(candidate_date, time_of_day, tzinfo=_KST)
        if candidate_dt >= current:
            return candidate_dt
    return datetime.combine(current.date() + timedelta(days=1), time_of_day, tzinfo=_KST)


def _format_local_datetime(value: datetime) -> str:
    return _ensure_kst_datetime(value).isoformat(timespec="seconds")


def _parse_local_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return _ensure_kst_datetime(parsed)


def _ensure_kst_datetime(value: datetime | None) -> datetime:
    if value is None:
        return _now_kst()
    if value.tzinfo is None:
        return value.replace(tzinfo=_KST)
    return value.astimezone(_KST)


def _safe_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError:
        return str(value)


def _unique_strings(items: list[str]) -> list[str]:
    normalized_items: list[str] = []
    seen: set[str] = set()
    for item in items:
        normalized = str(item or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        normalized_items.append(normalized)
    return normalized_items


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _iso_now() -> str:
    return _now_kst().isoformat(timespec="seconds")


def _now_kst() -> datetime:
    return datetime.now(_KST)


_SERVICE: JobSchedulerService | None = None


def get_job_scheduler_service() -> JobSchedulerService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = JobSchedulerService()
    return _SERVICE


def reset_job_scheduler_service_for_tests(
    *,
    state_path: Path | None = None,
    output_dir: Path | None = None,
    runner: PipelineRunner | None = None,
    poll_interval_seconds: float = _DEFAULT_POLL_INTERVAL_SECONDS,
) -> JobSchedulerService:
    global _SERVICE
    if _SERVICE is not None:
        _SERVICE.shutdown()
    _SERVICE = JobSchedulerService(
        state_path=state_path,
        output_dir=output_dir,
        runner=runner,
        poll_interval_seconds=poll_interval_seconds,
    )
    return _SERVICE


def parse_seed_keywords(seed_keywords: list[str] | None = None, seed_keywords_text: str = "") -> list[str]:
    items = [str(item or "") for item in (seed_keywords or [])]
    text_items = parse_keyword_text(seed_keywords_text)
    return _unique_strings([*items, *text_items])
