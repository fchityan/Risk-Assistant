"""FastAPI application for reputation screening."""

import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from logging_config import configure_logging, get_logger
from orchestrator import (
    claim_clarification_resume,
    generate_run_id,
    load_final_report,
    load_run_status,
    resume_pipeline,
    run_pipeline,
    save_run_status,
)
from schemas.report import ScreenRequest
from schemas.resolution import ClarificationRequest
from stages.llm_client import llm_configured
from stages.stage5_rules import generate_kimi_memo_from_report, generate_sensenova_memo_from_report

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    logger.info(
        "API starting agent_version=%s log_level=%s llm_provider=%s",
        settings.agent_version,
        settings.log_level,
        settings.llm_provider,
    )
    yield
    logger.info("API shutdown")


app = FastAPI(
    title="Reputation Screening Agent",
    description="Public-source reputational screening pipeline",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8501",
        "http://127.0.0.1:8501",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    try:
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "%s %s -> %s (%.0fms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response
    except Exception:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.exception(
            "%s %s failed after %.0fms",
            request.method,
            request.url.path,
            elapsed_ms,
        )
        raise


def _is_key_present(key: str) -> bool:
    return bool(key) and not key.startswith("YOUR_")


@app.get("/health")
async def health():
    settings = get_settings()
    return {
        "status": "ok",
        "secrets": {
            "bright_data_api_key": settings.serp_configured or bool(
                settings.bright_data_api_key and not settings.bright_data_api_key.startswith("YOUR_")
            ),
            "bright_data_serp": settings.serp_configured,
            "bright_data_serp_zone": settings.bright_data_serp_zone if settings.serp_configured else None,
            "bright_data_browser": settings.browser_configured,
            "bright_data_browser_zone": settings.bright_data_browser_zone or None,
            "bright_data_browser_username_set": bool(settings.bright_data_browser_username),
            "bright_data_customer_id_set": bool(settings.bright_data_customer_id),
            "llm_provider": settings.llm_provider,
            "llm_configured": llm_configured(),
            "tokenrouter": _is_key_present(settings.tokenrouter_api_key),
            "tokenrouter_model": settings.tokenrouter_model,
            "openrouter": _is_key_present(settings.openrouter_api_key),
            "openrouter_model": settings.openrouter_model,
            "kimi": _is_key_present(settings.kimi_api_key),
            "sensenova": _is_key_present(settings.sensenova_api_key),
            "sensenova_model": settings.sensenova_model,
            "sensenova_configured": settings.sensenova_configured,
            "daytona": _is_key_present(settings.daytona_api_key),
        },
        "bright_data_note": (
            "SERP: BRIGHT_DATA_API_KEY + BRIGHT_DATA_SERP_ZONE. "
            "Browser: BRIGHT_DATA_BROWSER_USERNAME + PASSWORD "
            "(or CUSTOMER_ID + BROWSER_ZONE + PASSWORD)."
        ),
    }


@app.post("/screen")
async def create_screening(req: ScreenRequest, background_tasks: BackgroundTasks):
    run_id = generate_run_id()
    save_run_status(run_id, "queued")
    logger.info(
        "[%s] screening queued subject_type=%s primary_name=%s",
        run_id,
        req.subject_type.value,
        req.primary_name,
    )
    background_tasks.add_task(run_pipeline, run_id, req)
    return {"run_id": run_id, "status": "queued"}


@app.get("/screen/{run_id}")
async def get_screening(run_id: str):
    status = await asyncio.to_thread(load_run_status, run_id)
    if status is None:
        logger.warning("GET /screen/%s not found", run_id)
        raise HTTPException(status_code=404, detail="Run not found")

    if status["status"] == "complete":
        report = await asyncio.to_thread(load_final_report, run_id)
        if report is None:
            logger.error("[%s] complete status but final_report.json missing", run_id)
            raise HTTPException(status_code=500, detail="Report missing for completed run")
        return {
            "run_id": run_id,
            "status": "complete",
            "report": report,
        }

    if status["status"] == "clarification_required":
        return {
            "run_id": run_id,
            "status": "clarification_required",
            "stage": status.get("stage"),
            "message": "Entity identity is ambiguous; analyst clarification required before screening continues.",
            "clarification_form": status.get("clarification"),
            "entity_resolution": status.get("entity_resolution"),
        }

    return {
        "run_id": run_id,
        "status": status["status"],
        "stage": status.get("stage"),
        "error": status.get("error"),
    }


@app.post("/screen/{run_id}/clarify")
async def clarify_screening(
    run_id: str,
    clarification: ClarificationRequest,
    background_tasks: BackgroundTasks,
):
    status = await asyncio.to_thread(load_run_status, run_id)
    if status is None:
        logger.warning("POST /screen/%s/clarify run not found", run_id)
        raise HTTPException(status_code=404, detail="Run not found")

    claimed = await asyncio.to_thread(claim_clarification_resume, run_id)
    if not claimed:
        current = await asyncio.to_thread(load_run_status, run_id)
        current_status = current.get("status") if current else "unknown"
        logger.warning(
            "[%s] clarify rejected current_status=%s",
            run_id,
            current_status,
        )
        raise HTTPException(
            status_code=409,
            detail=f"Run is not awaiting clarification (current status: {current_status})",
        )

    logger.info(
        "[%s] clarification received country=%s candidate_id=%s",
        run_id,
        clarification.country,
        clarification.candidate_id,
    )
    background_tasks.add_task(resume_pipeline, run_id, clarification)
    return {
        "run_id": run_id,
        "status": "running",
        "stage": "entity_resolution",
    }


@app.post("/screen/{run_id}/memo/sensenova")
async def generate_sensenova_memo(run_id: str):
    status = await asyncio.to_thread(load_run_status, run_id)
    if status is None:
        logger.warning("POST /screen/%s/memo/sensenova run not found", run_id)
        raise HTTPException(status_code=404, detail="Run not found")

    if status.get("status") != "complete":
        raise HTTPException(
            status_code=409,
            detail=f"Run is not complete (current status: {status.get('status')})",
        )

    report = await asyncio.to_thread(load_final_report, run_id)
    if report is None:
        logger.error("[%s] memo generation requested but final_report.json missing", run_id)
        raise HTTPException(status_code=500, detail="Report missing for completed run")

    try:
        memo = await asyncio.to_thread(generate_sensenova_memo_from_report, report)
        return {
            "run_id": run_id,
            "source": "sensenova",
            "memo": memo,
        }
    except RuntimeError as exc:
        logger.warning("[%s] SenseNova memo generation rejected: %s; falling back to Kimi", run_id, exc)
        try:
            memo = await asyncio.to_thread(generate_kimi_memo_from_report, report)
            return {
                "run_id": run_id,
                "source": "kimi",
                "memo": memo,
                "fallback_reason": str(exc),
            }
        except Exception as kimi_exc:
            logger.exception("[%s] Kimi fallback memo generation failed", run_id)
            raise HTTPException(
                status_code=502,
                detail=(
                    "SenseNova failed and Kimi fallback failed. "
                    f"SenseNova error: {exc}; Kimi error: {kimi_exc}"
                ),
            ) from kimi_exc
    except Exception as exc:
        msg = str(exc)
        logger.warning("[%s] SenseNova memo generation failed: %s; falling back to Kimi", run_id, msg)
        try:
            memo = await asyncio.to_thread(generate_kimi_memo_from_report, report)
            return {
                "run_id": run_id,
                "source": "kimi",
                "memo": memo,
                "fallback_reason": msg,
            }
        except Exception as kimi_exc:
            logger.exception("[%s] Kimi fallback memo generation failed", run_id)
            if "Error code: 401" in msg or "Forbidden" in msg:
                raise HTTPException(
                    status_code=401,
                    detail=(
                        "SenseNova authorization failed (401 Forbidden), and Kimi fallback failed. "
                        f"Kimi error: {kimi_exc}"
                    ),
                ) from kimi_exc
            raise HTTPException(
                status_code=502,
                detail=(
                    "SenseNova request failed and Kimi fallback failed. "
                    f"SenseNova error: {exc}; Kimi error: {kimi_exc}"
                ),
            ) from kimi_exc
