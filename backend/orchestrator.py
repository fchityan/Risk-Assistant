"""Pipeline orchestrator with checkpointing."""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from config import get_settings
from logging_config import get_logger
from schemas.report import ReputationScreeningReport, ScreenRequest
from schemas.resolution import ClarificationRequest, RunStatusValue
from stages.stage1_subject import run_stage1
from stages.stage1b_resolve import run_stage1b
from stages.stage2_collect import run_stage2
from stages.stage3_sandbox import run_stage3
from stages.stage4_llm import run_stage4
from stages.stage5_rules import run_stage5

logger = get_logger(__name__)

STAGE_FILES = {
    "subject_prep": "checkpoint_subject_prep.json",
    "entity_resolution": "checkpoint_entity_resolution.json",
    "data_collection": "checkpoint_data_collection.json",
    "sandbox_processing": "checkpoint_sandbox_processing.json",
    "llm_reasoning": "checkpoint_llm_reasoning.json",
    "rule_engine": "checkpoint_rule_engine.json",
}


def get_run_dir(run_id: str) -> Path:
    path = get_settings().runs_path / run_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_runs_dir() -> Path:
    runs_path = get_settings().runs_path
    runs_path.mkdir(parents=True, exist_ok=True)
    return runs_path


def generate_run_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d")
    runs_dir = ensure_runs_dir()
    existing = list(runs_dir.glob(f"RSR-{ts}-*"))
    seq = len(existing) + 1
    return f"RSR-{ts}-{seq:03d}"


def _atomic_write_json(path: Path, payload: dict) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    tmp_path.replace(path)


def save_run_status(
    run_id: str,
    status: RunStatusValue,
    stage: str | None = None,
    error: str | None = None,
    clarification: dict | None = None,
    entity_resolution: dict | None = None,
) -> None:
    run_dir = get_run_dir(run_id)
    payload: dict = {
        "run_id": run_id,
        "status": status,
        "stage": stage,
        "error": error,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if clarification is not None:
        payload["clarification"] = clarification
    if entity_resolution is not None:
        payload["entity_resolution"] = entity_resolution
    _atomic_write_json(run_dir / "status.json", payload)
    if status == "error":
        logger.error("[%s] status=error error=%s", run_id, error)
    else:
        logger.info("[%s] status=%s stage=%s", run_id, status, stage)


def load_run_status(run_id: str) -> dict | None:
    status_path = get_settings().runs_path / run_id / "status.json"
    if not status_path.exists():
        return None
    with open(status_path, encoding="utf-8") as f:
        return json.load(f)


def save_final_report(run_id: str, report: dict) -> None:
    run_dir = get_run_dir(run_id)
    _atomic_write_json(run_dir / "final_report.json", report)
    logger.info("[%s] final_report.json written", run_id)


def load_final_report(run_id: str) -> dict | None:
    report_path = get_settings().runs_path / run_id / "final_report.json"
    if not report_path.exists():
        return None
    with open(report_path, encoding="utf-8") as f:
        return json.load(f)


def run_or_load(stage_name: str, run_id: str, fn) -> dict:
    run_dir = get_run_dir(run_id)
    filename = STAGE_FILES[stage_name]
    path = run_dir / filename

    if path.exists():
        logger.info("[%s] stage=%s loaded checkpoint %s", run_id, stage_name, filename)
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    logger.info("[%s] stage=%s running", run_id, stage_name)
    start = time.perf_counter()
    try:
        result = fn()
    except Exception:
        logger.exception("[%s] stage=%s failed after %.1fs", run_id, stage_name, time.perf_counter() - start)
        raise

    elapsed = time.perf_counter() - start
    _atomic_write_json(path, result)
    logger.info("[%s] stage=%s complete (%.1fs) checkpoint=%s", run_id, stage_name, elapsed, filename)
    return result


def _run_stages_2_to_5(run_id: str, checkpoint: dict) -> None:
    save_run_status(run_id, "running", stage="data_collection")

    cp2 = run_or_load(
        "data_collection",
        run_id,
        lambda: run_stage2(checkpoint),
    )
    save_run_status(run_id, "running", stage="sandbox_processing")

    cp3 = run_or_load(
        "sandbox_processing",
        run_id,
        lambda: run_stage3(cp2),
    )
    save_run_status(run_id, "running", stage="llm_reasoning")

    cp4 = run_or_load(
        "llm_reasoning",
        run_id,
        lambda: run_stage4(cp3),
    )
    save_run_status(run_id, "running", stage="rule_engine")

    cp5 = run_or_load(
        "rule_engine",
        run_id,
        lambda: run_stage5(cp4),
    )

    report_dict = cp5["report"]
    ReputationScreeningReport.model_validate(report_dict)
    save_final_report(run_id, report_dict)
    save_run_status(run_id, "complete", stage="rule_engine")


def run_pipeline(run_id: str, req: ScreenRequest) -> None:
    logger.info("[%s] pipeline started", run_id)
    try:
        save_run_status(run_id, "running", stage="subject_prep")

        cp1 = run_or_load(
            "subject_prep",
            run_id,
            lambda: run_stage1(run_id, req),
        )
        save_run_status(run_id, "running", stage="entity_resolution")

        cp1b = run_or_load(
            "entity_resolution",
            run_id,
            lambda: run_stage1b(cp1),
        )

        entity_res = cp1b.get("entity_resolution", {})
        if entity_res.get("action") == "clarification_required":
            logger.info(
                "[%s] pausing for clarification ambiguity=%s reasons=%s",
                run_id,
                entity_res.get("ambiguity_level"),
                entity_res.get("reason_codes"),
            )
            save_run_status(
                run_id,
                "clarification_required",
                stage="entity_resolution",
                clarification=cp1b.get("clarification_form"),
                entity_resolution=entity_res,
            )
            return

        _run_stages_2_to_5(run_id, cp1b)
        logger.info("[%s] pipeline complete", run_id)
    except Exception as e:
        logger.exception("[%s] pipeline failed: %s", run_id, e)
        save_run_status(run_id, "error", error=str(e))
        raise


def resume_pipeline(run_id: str, clarification: ClarificationRequest | dict) -> None:
    logger.info("[%s] pipeline resume after clarification", run_id)
    try:
        save_run_status(run_id, "running", stage="entity_resolution")
        run_dir = get_run_dir(run_id)

        cp1_path = run_dir / STAGE_FILES["subject_prep"]
        with open(cp1_path, encoding="utf-8") as f:
            cp1 = json.load(f)

        cp1b_path = run_dir / STAGE_FILES["entity_resolution"]
        prior_candidates: list = []
        prior_inferred: dict = {}
        if cp1b_path.exists():
            with open(cp1b_path, encoding="utf-8") as f:
                old_cp1b = json.load(f)
            prior_candidates = old_cp1b.get("candidate_entities", [])
            prior_resolved = old_cp1b.get("resolved_subject", {})
            prior_inferred = prior_resolved.get("inferred", {})

        clar = (
            clarification
            if isinstance(clarification, ClarificationRequest)
            else ClarificationRequest.model_validate(clarification)
        )

        cp1_augmented = {
            **cp1,
            "prior_candidate_entities": prior_candidates,
            "prior_inferred": prior_inferred,
        }
        cp1b = run_stage1b(cp1_augmented, clar)
        _atomic_write_json(cp1b_path, cp1b)

        _run_stages_2_to_5(run_id, cp1b)
        logger.info("[%s] pipeline complete after clarification", run_id)
    except Exception as e:
        logger.exception("[%s] pipeline resume failed: %s", run_id, e)
        save_run_status(run_id, "error", error=str(e))
        raise
