import html
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import streamlit as st

from api_client import (
    build_screen_request,
    generate_sensenova_memo,
    get_health,
    get_screen_status,
    start_screening,
    submit_clarification,
)
from report_adapter import load_report_from_path, normalize_ui_data
from services.bright_data import bright_data_configured, collect_public_data
from services.llm_reasoning import KIMI_API_KEY, analyze_with_llm
from services.sensenova import generate_memo
from settings import get_frontend_settings

st.set_page_config(
    page_title="Risk Assistant",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

FRONTEND_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_PATH = FRONTEND_DIR.parent / "docs" / "examples" / "example-profile.json"
SETTINGS = get_frontend_settings()
SUBJECT_TYPES = ["Company", "Private Company", "Individual", "HNW Prospect", "Vendor", "Key Person"]


def _api_to_ui_subject_type(value: str) -> str:
    return "Individual" if (value or "").lower() == "individual" else "Company"


def _format_disposition(value: str | None) -> str:
    if not value:
        return ""
    return value.replace("_", " ").title()


def _trunc(text: str, max_len: int = 64) -> str:
    if not text:
        return ""
    return text if len(text) <= max_len else text[: max_len - 3] + "..."


def _fmt_value(value) -> str:
    if value is None:
        return "None"
    if isinstance(value, list):
        return html.escape(", ".join(str(v) for v in value)) if value else "None"
    text = str(value).strip()
    return html.escape(text) if text else "None"


_COUNTRY_FLAGS = {
    "singapore": "🇸🇬", "united states": "🇺🇸", "usa": "🇺🇸", "us": "🇺🇸",
    "united kingdom": "🇬🇧", "uk": "🇬🇧", "china": "🇨🇳", "hong kong": "🇭🇰",
    "australia": "🇦🇺", "germany": "🇩🇪", "france": "🇫🇷", "india": "🇮🇳",
    "japan": "🇯🇵", "canada": "🇨🇦", "brazil": "🇧🇷", "russia": "🇷🇺",
    "uae": "🇦🇪", "malaysia": "🇲🇾", "indonesia": "🇮🇩", "thailand": "🇹🇭",
    "south korea": "🇰🇷", "netherlands": "🇳🇱", "switzerland": "🇨🇭",
}

def _fmt_country(value) -> str:
    if not value or value == "None":
        return "None"
    text = str(value).strip()
    flag = _COUNTRY_FLAGS.get(text.lower(), "")
    return f"{flag}&nbsp;{html.escape(text)}" if flag else html.escape(text)


def _kv_rows(pairs: list[tuple[str, str]]) -> str:
    rows = []
    for label, value in pairs:
        rows.append(
            f"<div class='kv-row'><div class='kv-label'>{html.escape(label)}</div><div class='kv-value'>{value}</div></div>"
        )
    return "".join(rows)


def _init_state() -> None:
    if "ui_data" not in st.session_state:
        st.session_state.ui_data = load_report_from_path(DEFAULT_DATA_PATH)
    if "polling" not in st.session_state:
        st.session_state.polling = False
    if "active_run_id" not in st.session_state:
        st.session_state.active_run_id = None
    if "poll_deadline" not in st.session_state:
        st.session_state.poll_deadline = 0.0
    if "last_poll_time" not in st.session_state:
        st.session_state.last_poll_time = 0.0
    if "clarification_pending" not in st.session_state:
        st.session_state.clarification_pending = None
    if "last_success" not in st.session_state:
        st.session_state.last_success = None
    if "show_full_memo" not in st.session_state:
        st.session_state.show_full_memo = False
    if "memo_source" not in st.session_state:
        st.session_state.memo_source = "report"
    if "effective_use_mock_data" not in st.session_state:
        st.session_state.effective_use_mock_data = SETTINGS["use_mock_data"]
    if "backend_available" not in st.session_state:
        st.session_state.backend_available = False
    if "backend_status_message" not in st.session_state:
        st.session_state.backend_status_message = ""
    if "kimi_api_key_set" not in st.session_state:
        st.session_state.kimi_api_key_set = SETTINGS.get("kimi_api_key_set", False)
    if "daytona_api_key_set" not in st.session_state:
        st.session_state.daytona_api_key_set = SETTINGS.get("daytona_api_key_set", False)
    if "backend_url" not in st.session_state:
        st.session_state.backend_url = SETTINGS["backend_url"]
    if "frontend_live_mode" not in st.session_state:
        st.session_state.frontend_live_mode = False


def _backend_url() -> str:
    url = (st.session_state.get("backend_url") or SETTINGS["backend_url"]).strip()
    return url.rstrip("/")


def _resolve_data_source() -> None:
    backend_url = _backend_url()
    host = (urlparse(backend_url).hostname or "").lower()
    localhost_backend = host in {"127.0.0.1", "localhost"}

    if _frontend_live_configured():
        st.session_state.effective_use_mock_data = False
        st.session_state.backend_available = False
        st.session_state.frontend_live_mode = True
        st.session_state.kimi_api_key_set = True
        st.session_state.backend_status_message = (
            "Live mode connected."
        )
        return

    if SETTINGS.get("use_mock_data_forced_by_cloud_localhost") and localhost_backend:
        st.session_state.effective_use_mock_data = True
        st.session_state.backend_available = False
        st.session_state.frontend_live_mode = False
        st.session_state.backend_status_message = (
            "Mock mode forced: BACKEND_URL points to localhost on Streamlit Cloud. "
            "Set BACKEND_URL to a public API URL for live screening."
        )
        return

    if SETTINGS["use_mock_data"]:
        st.session_state.effective_use_mock_data = True
        st.session_state.backend_available = False
        st.session_state.frontend_live_mode = False
        st.session_state.backend_status_message = "Mock mode forced by USE_MOCK_DATA=true."
        return

    try:
        health = get_health(backend_url)
        if health.get("status") == "ok":
            st.session_state.effective_use_mock_data = False
            st.session_state.backend_available = True
            st.session_state.frontend_live_mode = False
            secrets = health.get("secrets", {}) if isinstance(health, dict) else {}
            if isinstance(secrets, dict):
                st.session_state.kimi_api_key_set = bool(secrets.get("kimi"))
                st.session_state.daytona_api_key_set = bool(secrets.get("daytona"))
            st.session_state.backend_status_message = f"Connected to API at {backend_url}."
            return
        st.session_state.effective_use_mock_data = True
        st.session_state.backend_available = False
        st.session_state.backend_status_message = (
            "API health check did not return status=ok; using mock data."
        )
    except Exception as exc:
        st.session_state.effective_use_mock_data = True
        st.session_state.backend_available = False
        st.session_state.backend_status_message = (
            f"Could not reach API at {backend_url}; using mock data ({exc})."
        )


def _fallback_to_mock(reason: str) -> None:
    st.session_state.effective_use_mock_data = True
    st.session_state.backend_available = False
    st.session_state.frontend_live_mode = False
    st.session_state.backend_status_message = f"Live API unavailable; using mock data ({reason})."


def _frontend_live_configured() -> bool:
    return bool((KIMI_API_KEY or "").strip()) and bright_data_configured()


def _run_frontend_live_screening(
    subject_name: str,
    subject_type: str,
    country: str,
    purpose: str,
    role: str,
) -> dict:
    ui = load_report_from_path(DEFAULT_DATA_PATH)

    subject_payload = {
        "name": subject_name,
        "type": subject_type,
        "country": country,
        "screeningPurpose": purpose,
        "role": role,
    }
    public_sources = collect_public_data(subject_name, country)
    analysis = analyze_with_llm(subject_payload, public_sources)
    memo_payload = generate_memo(subject_payload, analysis)

    risk = analysis.get("riskSummary") if isinstance(analysis, dict) else {}
    findings = analysis.get("keyFindings") if isinstance(analysis, dict) else []
    steps = analysis.get("recommendedNextSteps") if isinstance(analysis, dict) else []
    risk = risk if isinstance(risk, dict) else {}
    findings = findings if isinstance(findings, list) else []
    steps = steps if isinstance(steps, list) else []

    ui["subject"] = {
        "name": subject_name,
        "type": "individual" if subject_type.lower() == "individual" else "organization",
        "country": country,
        "screeningPurpose": purpose,
        "role": role,
    }

    risk_score = int(risk.get("overallRiskScore", 58) or 58)
    ui["riskSummary"].update(
        {
            "riskCategory": risk.get("riskCategory", ui["riskSummary"].get("riskCategory", "Moderate Risk")),
            "confidenceScore": int(risk.get("confidenceScore", ui["riskSummary"].get("confidenceScore", 70)) or 70),
            "recommendation": risk.get("recommendation", ui["riskSummary"].get("recommendation", "Proceed with Conditions")),
            "summary": risk.get("summary", ui["riskSummary"].get("summary", "")),
            "supportSummaryLine": f"{max(1, min(5, len(findings)))} high / 0 med / 0 low",
        }
    )

    ui["entityMatch"]["score"] = 85 if country else 70
    ui["entityMatch"]["level"] = "High" if country else "Medium"
    ui["entityMatch"]["rationale"] = "Live mode entity estimate from public-source evidence."

    evidence_rows = []
    for idx, src in enumerate(public_sources, start=1):
        evidence_rows.append(
            {
                "id": f"EV-{idx:03d}",
                "sourceName": src.get("sourceName", "Public source"),
                "sourceUrl": src.get("sourceUrl", ""),
                "sourceTier": "Open Web",
                "supportBand": "high" if idx <= 2 else "medium",
                "severity": "moderate",
                "corroboration": "single_source",
                "sourceSnippet": src.get("sourceSnippet", ""),
                "finding": src.get("sourceName", "Public signal"),
                "publicationDate": None,
                "humanAction": "Review",
                "entityMatch": "medium",
                "adverseSeverity": "moderate",
                "recency": "unknown",
                "jurisdictionRelevance": "medium",
                "caseLinkage": "uncertain",
                "supportRuleTriggered": "manual_live_mode",
            }
        )

    ui["evidenceTable"] = evidence_rows
    ui["keyFindings"] = findings or ui.get("keyFindings", [])
    ui["recommendedNextSteps"] = steps or ui.get("recommendedNextSteps", [])
    ui["memo"]["body"] = memo_payload.get("body") or risk.get("summary") or ui["memo"].get("body", "")
    ui["memo"]["disclaimer"] = (
        "Live mode: Bright Data + Kimi via Streamlit. Human compliance review required."
    )

    now = datetime.now(timezone.utc).isoformat()
    synthetic_id = f"ID-{int(time.time())}"
    ui.setdefault("reportMetadata", {})
    ui["reportMetadata"].update(
        {
            "report_id": synthetic_id,
            "generated_at": now,
            "workflow_run_id": synthetic_id,
            "agent_version": "live-mode",
            "data_sources": ["bright_data_serp", "kimi"],
        }
    )
    ui.setdefault("assessmentRaw", {})
    ui["assessmentRaw"].update(
        {
            "overall_risk_level": "high" if risk_score >= 75 else "medium" if risk_score >= 45 else "low",
            "overall_summary": risk.get("summary", "Live screening completed."),
            "recommended_disposition": (risk.get("recommendation") or "Proceed with Conditions").replace(" ", "_"),
            "disposition_rationale": "Generated via frontend direct Kimi reasoning from Bright Data evidence.",
            "coverage_assessment": "moderate",
            "memo": ui["memo"]["body"],
        }
    )
    ui["riskFlags"] = [
        {
            "title": f.get("title", "Potential reputational signal"),
            "category": f.get("category", "Adverse Media"),
            "severity": (f.get("severity", "Moderate") or "Moderate").lower(),
            "description": f.get("description", "Requires analyst review."),
        }
        for f in findings
    ]
    return ui


def _poll_if_needed() -> None:
    if not st.session_state.polling or st.session_state.effective_use_mock_data:
        return

    run_id = st.session_state.active_run_id
    now = time.time()
    if not run_id:
        st.session_state.polling = False
        return
    if now > st.session_state.poll_deadline:
        st.session_state.polling = False
        st.error(f"Run {run_id} timed out after {int(SETTINGS['poll_timeout_seconds'])}s")
        return
    if now - st.session_state.last_poll_time < SETTINGS["poll_interval_seconds"]:
        time.sleep(0.4)
        st.rerun()

    try:
        status = get_screen_status(_backend_url(), run_id)
        st.session_state.last_poll_time = now
        state = status.get("status")

        if state == "complete":
            report = status.get("report")
            if not report:
                raise RuntimeError("Backend returned complete status without report payload")
            st.session_state.ui_data = normalize_ui_data(report)
            st.session_state.polling = False
            st.session_state.last_success = f"Screening complete ({run_id})."
            st.rerun()
        if state == "clarification_required":
            st.session_state.polling = False
            st.session_state.clarification_pending = status
            st.rerun()
        if state == "error":
            st.session_state.polling = False
            st.error(status.get("error") or "Pipeline failed")
        else:
            stage = status.get("stage") or "running"
            st.info(f"Run {run_id}: {state} - stage: {stage}")
            time.sleep(0.4)
            st.rerun()
    except Exception as exc:
        st.session_state.polling = False
        _fallback_to_mock(str(exc))
        st.session_state.ui_data = load_report_from_path(DEFAULT_DATA_PATH)
        st.session_state.last_success = "Live API became unavailable during polling. Loaded mock data instead."
        st.rerun()


_init_state()
_resolve_data_source()
_poll_if_needed()


data = st.session_state.ui_data
subject = data["subject"]
risk = data["riskSummary"]
entity = data["entityMatch"]
memo = data["memo"]
assessment = data.get("assessment", {})
determination = assessment.get("determination_basis", {})
support_summary = determination.get("support_summary", {})
triggered_rules = determination.get("triggered_rules", [])
report_metadata = data.get("reportMetadata", {})
schema_subject = data.get("schemaSubject", {})
screening_scope = data.get("screeningScope", {})
rubric_definition = data.get("rubricDefinition", {})
risk_flags = data.get("riskFlags", [])
evidence_raw = data.get("evidenceRaw", data.get("evidence", []))
analyst_checklist = data.get("analystChecklistRaw", data.get("analyst_checklist", []))
audit_trail_raw = data.get("auditTrailRaw", data.get("audit_trail", {}))

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Manrope:wght@400;500;600;700;800&display=swap');
.stApp { font-family: 'Manrope', sans-serif; background: #ffffff; }
header[data-testid="stHeader"] { display: block !important; background: transparent !important; }
button[kind="headerNoPadding"] { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; visibility: hidden !important; }
[data-testid="stSidebarCollapseButton"] { display: none !important; }
div[data-testid="stAppViewContainer"] { background: #ffffff; }
h1,h2,h3,h4,h5 { font-family: 'Space Grotesk', sans-serif !important; color: #1a2f5e; }
:root { --assessment-header-size: 24px; --assessment-header-weight: 700; --assessment-header-color: #1a2f5e; }
h3, h4 { font-size: var(--assessment-header-size) !important; font-weight: var(--assessment-header-weight) !important; line-height: 1.2; color: var(--assessment-header-color) !important; }
.header-standard { font-family: 'Space Grotesk', sans-serif !important; font-size: var(--assessment-header-size); font-weight: var(--assessment-header-weight); color: var(--assessment-header-color); line-height: 1.2; }
section[data-testid="stSidebar"] { background: linear-gradient(190deg, #061a3a 0%, #0a2d5d 58%, #07214a 100%) !important; border-right: 1px solid rgba(180,210,255,0.25); }
section[data-testid="stSidebar"] * { color: #edf4ff !important; }
section[data-testid="stSidebar"] .block-container { padding: 16px 14px 16px 14px !important; }
.block-container { max-width: 1550px !important; padding-top: 0.85rem !important; }
.hero { border: 1px solid #d5e3fb; border-radius: 18px; padding: 16px; margin-bottom: 10px; background: radial-gradient(circle at 95% 5%, rgba(15,157,141,0.16), transparent 35%), #fff; box-shadow: 0 14px 28px rgba(24,47,82,0.06); }
.main-title { font-size: 49px; font-weight: 700; color: #1f2f5b; line-height: 1.05; margin-bottom: 4px; }
.main-subtitle { color: #36527b; font-size: 13px; margin-bottom: 6px; }
.chip-row { display: flex; flex-wrap: wrap; gap: 6px; }
.chip { display: inline-flex; align-items: center; font-size: 10.5px; font-weight: 700; padding: 4px 10px; margin: 0; border: 1px solid #cfe0fb; border-radius: 999px; background: #f7fbff; color: #2c4f80; }
.metric-card { background: #fff; border: 1px solid #d2e2fb; border-radius: 14px; padding: 10px 12px; min-height: 94px; box-shadow: 0 8px 18px rgba(24,47,82,0.07); }
.metric-top { display: flex; align-items: center; gap: 8px; margin-bottom: 3px; }
.metric-icon { width: 32px; height: 32px; border-radius: 10px; display: inline-flex; align-items: center; justify-content: center; font-size: 17px; flex-shrink: 0; }
.i-risk { background: #e8f0ff; }
.i-evidence { background: #efe7ff; }
.i-entity { background: #def7ef; }
.i-coverage { background: #ece9ff; }
.i-disposition { background: #def7f6; }
.metric-label { font-size: 11px; color: #597294; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; }
.metric-v1 { color: #c55e31; font-size: 17px; font-weight: 800; }
.metric-v2 { color: #cc4e68; font-size: 15px; font-weight: 800; white-space: nowrap; }
.metric-v3 { color: #129069; font-size: 22px; font-weight: 800; }
.metric-v4 { color: #2d6be3; font-size: 19px; font-weight: 800; }
.metric-v5 { color: #0f9d8d; font-size: 13px; font-weight: 800; line-height: 1.3; }
.metric-caption { color: #5f7798; font-size: 10.5px; margin-top: 3px; }
.panel { background: #fff; border: 1px solid #d6e5fb; border-radius: 14px; padding: 12px; box-shadow: 0 8px 18px rgba(24,47,82,0.08); }
[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 14px !important; border: 1px solid #d6e5fb !important; background: #ffffff !important; box-shadow: none !important; padding: 8px 12px 12px 12px !important; }
[data-testid="stVerticalBlockBorderWrapper"] > div { background: #ffffff !important; }
[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stVerticalBlock"] { background: #ffffff !important; }
.form-card { background:#ffffff; border:1px solid #d6e3f5; border-radius:12px; padding:8px 10px; box-shadow: 0 6px 14px rgba(24,47,82,0.06); margin-bottom:10px; }
.rule-box { background: #f8fbff; border: 1px solid #d8e6fc; border-left: 3px solid #2d6be3; border-radius: 8px; padding: 8px; margin-bottom: 6px; font-size: 12px; }
.kf-shell { margin-top: 10px; border: 1px solid #dce6f7; border-radius: 12px; background: #ffffff; overflow: hidden; }
.kf-head { display: flex; align-items: center; gap: 10px; padding: 10px 12px; border-bottom: 1px solid #e8eef8; }
.kf-head-icon { width: 22px; height: 22px; border-radius: 7px; background: linear-gradient(160deg,#2f7de1,#1c62d6); color: #ffffff; display: inline-flex; align-items: center; justify-content: center; font-size: 12px; }
.kf-head-title { font-family: 'Space Grotesk', sans-serif !important; font-size: 20px; font-weight: var(--assessment-header-weight); color: var(--assessment-header-color); line-height: 1.2; }
.kf-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 10px 12px; border-top: 1px solid #edf2fb; }
.kf-left { display: flex; align-items: center; gap: 8px; min-width: 0; }
.kf-chevron { color: #7d91ad; font-size: 15px; line-height: 1; }
.kf-title { font-size: 13px; color: #2a3a54; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.kf-sev { font-size: 13px; font-weight: 700; display: inline-flex; align-items: center; gap: 5px; flex-shrink: 0; }
.kf-dot { font-size: 11px; line-height: 1; }
.kf-sev-high { color: #eb3131; }
.kf-sev-medium { color: #d78619; }
.kf-sev-low { color: #1d9a64; }
.kf-empty { padding: 12px; color: #5e7392; font-size: 13px; }
.kf-shell .streamlit-expanderHeader { font-size: 13px !important; color: #2a3a54 !important; font-weight: 500 !important; }
[data-testid="stExpander"] {
    border: 1px solid #dce6f7 !important;
    border-radius: 10px !important;
    background: #ffffff !important;
    margin-top: 8px !important;
    box-shadow: 0 2px 8px rgba(24,47,82,0.05) !important;
}
[data-testid="stExpander"] summary {
    color: #1f2f5b !important;
    font-weight: 700 !important;
    font-size: 14px !important;
    line-height: 1.35 !important;
    opacity: 1 !important;
}
[data-testid="stExpander"] summary p {
    color: #1f2f5b !important;
    opacity: 1 !important;
    margin: 0 !important;
}
[data-testid="stExpander"] summary svg {
    color: #7d91ad !important;
    opacity: 1 !important;
}
[data-testid="stExpanderDetails"] {
    color: #2a3a54 !important;
}
[data-testid="stExpanderDetails"] p,
[data-testid="stExpanderDetails"] li,
[data-testid="stExpanderDetails"] span,
[data-testid="stExpanderDetails"] div {
    color: #2a3a54 !important;
}
.memo-preview-title { font-size: 20px !important; }
.reviewer-decision-title { font-size: 20px !important; }
.ev-shell { margin-top: 6px; border: 1px solid #dce6f7; border-radius: 12px; background: #ffffff; padding: 10px; }
.ev-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.ev-title-wrap { display: flex; align-items: center; gap: 8px; }
.ev-icon { width: 22px; height: 22px; border-radius: 7px; background: linear-gradient(160deg,#56cf9b,#2da879); color: #ffffff; display: inline-flex; align-items: center; justify-content: center; font-size: 12px; }
.ev-title { font-size: 30px; }
.ev-viewall { border: 1px solid #e5eaf2; border-radius: 8px; background: #f8fafc; color: #8a96a7; font-size: 10px; font-weight: 600; padding: 4px 8px; }
.ev-table-wrap { border: 1px solid #e7edf7; border-radius: 8px; overflow: hidden; }
.ev-table { width: 100%; border-collapse: collapse; table-layout: fixed; }
.ev-table th { text-align: left; font-size: 12px; font-weight: 500; color: #7f8b9b; background: #f7f9fc; padding: 8px 10px; border-right: 1px solid #e7edf7; }
.ev-table th:last-child { border-right: none; }
.ev-table td { font-size: 13px; color: #2a3a54; padding: 8px 10px; border-top: 1px solid #e7edf7; border-right: 1px solid #e7edf7; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ev-table td:last-child { border-right: none; }
.ev-subrows { border: 1px solid #e7edf7; border-top: none; border-radius: 0 0 8px 8px; }
.ev-subrow { display: flex; align-items: center; gap: 10px; padding: 8px 10px; border-top: 1px solid #edf2fb; font-size: 13px; color: #2a3a54; }
.ev-subrow:first-child { border-top: none; }
.ev-chevron { color: #8b98ab; font-size: 15px; line-height: 1; }
.rf-shell { margin-top: 6px; border: 1px solid #dce6f7; border-radius: 12px; background: #ffffff; padding: 10px; }
.rf-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.rf-title-wrap { display: flex; align-items: center; gap: 8px; }
.rf-icon { width: 22px; height: 22px; border-radius: 7px; background: linear-gradient(160deg,#ff6a60,#f13c35); color: #ffffff; display: inline-flex; align-items: center; justify-content: center; font-size: 12px; }
.rf-viewall { border: 1px solid #e5eaf2; border-radius: 8px; background: #f8fafc; color: #8a96a7; font-size: 10px; font-weight: 600; padding: 4px 8px; }
.rf-table-wrap { border: 1px solid #e7edf7; border-radius: 8px; overflow: hidden; }
.rf-table { width: 100%; border-collapse: collapse; table-layout: fixed; }
.rf-table th { text-align: left; font-size: 12px; font-weight: 500; color: #7f8b9b; background: #f7f9fc; padding: 8px 10px; border-right: 1px solid #e7edf7; white-space: nowrap; }
.rf-table th:last-child { border-right: none; }
.rf-table td { font-size: 13px; color: #2a3a54; padding: 8px 10px; border-top: 1px solid #e7edf7; border-right: 1px solid #e7edf7; vertical-align: middle; }
.rf-table td:last-child { border-right: none; }
.rf-table th:nth-child(1), .rf-table td:nth-child(1) { width: 12%; white-space: nowrap; }
.rf-table th:nth-child(2), .rf-table td:nth-child(2) { width: 18%; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.rf-table th:nth-child(3), .rf-table td:nth-child(3) { width: 12%; white-space: nowrap; }
.rf-table th:nth-child(4), .rf-table td:nth-child(4) { width: 12%; white-space: nowrap; }
.rf-table th:nth-child(5), .rf-table td:nth-child(5) { width: 46%; }
.rf-table td:nth-child(5) { white-space: normal; word-break: break-word; line-height: 1.4; }
.rf-strong { font-weight: 700; }
.rf-badge { display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px; border-radius: 6px; font-size: 11px; font-weight: 600; white-space: nowrap; }
.rf-badge-high { background: #ffeceb; color: #e23a33; }
.rf-badge-status { background: #fff3dc; color: #c27d1d; }
.rbd-shell { margin-top: 14px; border: 1px solid #dce6f7; border-radius: 12px; background: #ffffff; padding: 10px; }
.rbd-head { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.rbd-icon { width: 22px; height: 22px; border-radius: 7px; background: linear-gradient(160deg,#8f79ff,#6f57db); color: #ffffff; display: inline-flex; align-items: center; justify-content: center; font-size: 12px; }
.rbd-method { margin-top: 6px; border: 1px solid #d7e2f7; border-radius: 8px; background: #f5f8ff; padding: 10px 12px; display: flex; align-items: center; justify-content: space-between; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; font-size: 12px; color: #2f3f59; }
.rbd-copy { font-size: 14px; color: #7b8ca6; }
.rbd-stats { margin-top: 10px; border: 1px solid #e7edf7; border-radius: 8px; background: #ffffff; display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); }
.rbd-stat { padding: 10px 8px; text-align: center; border-right: 1px solid #edf2fb; }
.rbd-stat:last-child { border-right: none; }
.rbd-label { font-size: 12px; color: #5f7290; margin-bottom: 4px; }
.rbd-value { font-size: 38px; font-weight: 700; line-height: 1; }
.rbd-high { color: #f04438; }
.rbd-medium { color: #f08c00; }
.rbd-low { color: #12a66a; }
.rbd-material { color: #2f6fed; }
.rbd-tier { color: #0f172a; }
.trg-shell { margin-top: 10px; border: 1px solid #dce6f7; border-radius: 12px; background: #ffffff; padding: 10px; }
.trg-head { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.trg-icon { width: 22px; height: 22px; border-radius: 7px; background: linear-gradient(160deg,#7aa4ff,#4d72f3); color: #ffffff; display: inline-flex; align-items: center; justify-content: center; font-size: 12px; }
.aud-shell { margin-top: 6px; border: 1px solid #dce6f7; border-radius: 12px; background: #ffffff; padding: 10px; max-width: 560px; }
.aud-head { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.aud-icon { width: 22px; height: 22px; border-radius: 7px; background: linear-gradient(160deg,#58d7a0,#2aa579); color: #ffffff; display: inline-flex; align-items: center; justify-content: center; font-size: 12px; }
.aud-table-wrap { border: 1px solid #e7edf7; border-radius: 8px; overflow: hidden; }
.aud-table { width: 100%; border-collapse: collapse; table-layout: fixed; }
.aud-table th { text-align: left; font-size: 12px; font-weight: 500; color: #7f8b9b; background: #f7f9fc; padding: 8px 10px; border-right: 1px solid #e7edf7; }
.aud-table th:last-child { border-right: none; }
.aud-table td { font-size: 12px; color: #2a3a54; padding: 8px 10px; border-top: 1px solid #e7edf7; border-right: 1px solid #e7edf7; vertical-align: top; word-break: break-word; }
.aud-table td:last-child { border-right: none; }
.fm-shell { margin-top: 6px; border: 1px solid #dce6f7; border-radius: 12px; background: #ffffff; padding: 10px; max-width: 560px; }
.fm-head { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.fm-icon { width: 22px; height: 22px; border-radius: 7px; background: linear-gradient(160deg,#66a9ff,#2f76df); color: #ffffff; display: inline-flex; align-items: center; justify-content: center; font-size: 12px; }
.fm-title { font-family: 'Space Grotesk', sans-serif !important; font-size: 30px; font-weight: 700; color: #1a2f5e; line-height: 1.2; }
.fm-subject { border: 1px solid #d7e2f7; border-radius: 8px; background: #f5f8ff; padding: 10px 12px; font-size: 12px; color: #2a3a54; margin-bottom: 10px; }
.fm-subject-value { color: #2f6fed; }
.fm-body { font-size: 13px; color: #2a3a54; line-height: 1.6; margin-bottom: 10px; }
.fm-disp { border: 1px solid #d7e2f7; border-radius: 8px; background: #f8fbff; padding: 10px 12px; }
.fm-disp-line { font-size: 13px; color: #2a3a54; margin-bottom: 6px; }
.fm-disp-body { font-size: 13px; color: #2a3a54; line-height: 1.6; }
.rub-shell { margin-top: 6px; border: 1px solid #dce6f7; border-radius: 12px; background: #ffffff; padding: 10px; }
.rub-head { display: flex; align-items: center; gap: 8px; margin-bottom: 2px; }
.rub-icon { width: 22px; height: 22px; border-radius: 7px; background: linear-gradient(160deg,#8b79ff,#6f57db); color: #ffffff; display: inline-flex; align-items: center; justify-content: center; font-size: 12px; }
.rub-version { font-size: 12px; color: #5f7290; margin: 2px 0 10px 30px; }
.rub-subtitle { font-family: 'Space Grotesk', sans-serif !important; font-size: 20px; font-weight: 700; color: #1a2f5e; margin: 8px 0 8px 0; }
.rub-table-wrap { border: 1px solid #e7edf7; border-radius: 8px; overflow: hidden; }
.rub-table { width: 100%; border-collapse: collapse; table-layout: fixed; }
.rub-table th { text-align: left; font-size: 12px; font-weight: 500; color: #7f8b9b; background: #f7f9fc; padding: 8px 10px; border-right: 1px solid #e7edf7; }
.rub-table th:last-child { border-right: none; }
.rub-table td { font-size: 13px; color: #2a3a54; padding: 8px 10px; border-top: 1px solid #e7edf7; border-right: 1px solid #e7edf7; }
.rub-table td:last-child { border-right: none; }
.rub-rules-grid { margin-top: 10px; display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.rub-rule-title { font-family: 'Space Grotesk', sans-serif !important; font-size: 18px; font-weight: 700; color: #1a2f5e; margin: 0 0 6px 0; }
.rub-rule-list { margin: 0; padding-left: 18px; }
.rub-rule-list li { font-size: 13px; color: #2a3a54; margin-bottom: 6px; }
.mock-badge { display: inline-block; padding: 3px 8px; border-radius: 6px; font-size: 10px; font-weight: 800; color: #1f2937; background: #f59e0b; margin-bottom: 8px; }
.mock-banner { background: #fff7df; border: 1px solid #f6c25f; color: #8b5a0b; border-radius: 8px; padding: 8px 12px; margin-bottom: 8px; font-size: 12px; font-weight: 700; }
.stButton > button { border-radius: 12px !important; border: 1px solid rgba(18,132,124,0.4) !important; background: linear-gradient(90deg,#1f70cf,#119385) !important; color: #fff !important; font-weight: 700 !important; width: 100% !important; }
.stTextInput > div > div > input,
.stTextArea textarea {
    border-radius: 12px !important;
    border: 1px solid #cadaf4 !important;
    background: #f8fbff !important;
    color: #1f2f5b !important;
    caret-color: #1f2f5b !important;
    -webkit-text-fill-color: #1f2f5b !important;
}
.stTextInput label,
.stSelectbox label,
.stTextArea label,
.stTextInput label p,
.stSelectbox label p,
.stTextArea label p {
    color: #2f466b !important;
    font-weight: 700 !important;
    opacity: 1 !important;
}
.stSelectbox div[data-baseweb="select"] > div {
    border-radius: 12px !important;
    border: 1px solid #cadaf4 !important;
    background: #f8fbff !important;
    color: #1f2f5b !important;
    box-shadow: none !important;
}
.stSelectbox div[data-baseweb="select"] input,
.stSelectbox div[data-baseweb="select"] div[role="combobox"] {
    border: none !important;
    background: transparent !important;
    box-shadow: none !important;
    color: #1f2f5b !important;
    caret-color: #1f2f5b !important;
    -webkit-text-fill-color: #1f2f5b !important;
}
.stTextInput > div > div > input::placeholder,
.stTextArea textarea::placeholder,
.stSelectbox div[data-baseweb="select"] input::placeholder {
    color: #6a7fa5 !important;
    opacity: 1 !important;
}
.stTextInput > div > div > input:focus,
.stTextArea textarea:focus,
.stSelectbox div[data-baseweb="select"] > div:focus-within {
    outline: none !important;
    border-color: #7aa7f0 !important;
    box-shadow: 0 0 0 2px rgba(47,111,237,0.18) !important;
}
@media (max-width: 1023px) {
    div[data-testid="stSidebarOverlay"] {
        background: transparent !important;
        opacity: 0 !important;
        pointer-events: none !important;
    }
    .block-container { padding-top: 0.35rem !important; }
    .hero { padding: 12px; margin-bottom: 8px; }
    .hero-right { display: none; }
    .main-title { font-size: 26px; line-height: 1.08; margin-bottom: 6px; }
    .main-subtitle { font-size: 17px; line-height: 1.45; margin-bottom: 10px; color: #29466f; }
    .chip-row { gap: 8px; }
    .chip { font-size: 11px; padding: 6px 10px; }
    [data-testid="stVerticalBlockBorderWrapper"] { padding: 6px 8px 8px 8px !important; }
    .assessment-shell { padding: 6px 2px; }
    .assessment-columns { grid-template-columns: 1fr; gap: 14px; }
    .assessment-col-right { border-left: none; padding-left: 0; }
    .scope-grid { grid-template-columns: 1fr; }
    .kv-row { grid-template-columns: 1fr; gap: 2px; margin: 10px 0; }
    .kv-label { font-size: 12px; }
    .kv-value { font-size: 14px; line-height: 1.45; color: #1f4fb5; }
    [data-testid="stExpander"] summary {
        font-size: 15px !important;
        line-height: 1.4 !important;
    }
    [data-testid="stExpander"] {
        border-radius: 12px !important;
        margin-top: 10px !important;
    }

    .stTextInput > div > div > input,
    .stTextArea textarea {
        background: #ffffff !important;
        color: #1f2f5b !important;
        -webkit-text-fill-color: #1f2f5b !important;
    }
    .stSelectbox div[data-baseweb="select"] > div {
        background: #ffffff !important;
    }
    .stSelectbox div[data-baseweb="select"] input,
    .stSelectbox div[data-baseweb="select"] div[role="combobox"] {
        background: transparent !important;
        color: #1f2f5b !important;
        -webkit-text-fill-color: #1f2f5b !important;
    }
}
.stTabs [data-baseweb="tab-list"] {
    gap: 6px;
    border-bottom: 1px solid #d7e2f4;
    padding-bottom: 0;
    margin-bottom: 0;
    background: #ffffff;
    border-radius: 16px 16px 0 0;
    border: 1px solid #dce6f7;
    border-bottom: none;
    padding: 0 16px;
    box-shadow: 0 -2px 8px rgba(24,47,82,0.03);
}
.stTabs [data-baseweb="tab-panel"] {
    background: #ffffff;
    border: 1px solid #dce6f7;
    border-top: none;
    border-radius: 0 0 16px 16px;
    padding: 16px 20px 20px 20px;
    box-shadow: 0 4px 16px rgba(24,47,82,0.06);
}
.stTabs [data-baseweb="tab"] {
    font-size: 16px;
    font-weight: 600;
    color: #3b4d72;
    padding: 10px 8px 12px 8px;
    border-bottom: 2px solid transparent;
    background: transparent;
}
.stTabs [aria-selected="true"] {
    color: #2b406a !important;
    border-bottom: 2px solid #2f6fed !important;
}
.hero-shield-wrap { text-align: center; padding-top: 2px; }
.hero-shield { width:120px; height:120px; margin:0 auto; border-radius:50%; background:radial-gradient(circle at 40% 35%, #61a4ff, #2456d6); color:#fff; display:flex; align-items:center; justify-content:center; font-size:62px; border:4px solid #e7efff; box-shadow:0 12px 22px rgba(35,73,151,0.22); }
.panel-title { font-family: 'Space Grotesk', sans-serif !important; font-size: var(--assessment-header-size); font-weight: var(--assessment-header-weight); color: var(--assessment-header-color); margin-bottom:8px; line-height: 1.2; }
.memo-snippet { font-size:12px; color:#3e5884; line-height:1.5; max-height:120px; overflow:hidden; }
.ghost-link { border:1px solid #d4e0f6; border-radius:9px; padding:8px 10px; font-size:12px; color:#2a5ac8; background:#f8fbff; display:inline-block; }
.assessment-shell { padding: 8px 8px; }
.assessment-head { display:flex; align-items:center; gap:12px; margin-bottom:10px; }
.assessment-icon { width:40px; height:40px; border-radius:11px; background:#e8f1ff; display:flex; align-items:center; justify-content:center; font-size:20px; flex-shrink:0; }
.assessment-title { font-family: 'Space Grotesk', sans-serif !important; font-size: var(--assessment-header-size); font-weight: var(--assessment-header-weight); color: var(--assessment-header-color); line-height:1.2; }
.assessment-summary { font-size:13.5px; color:#4a6180; margin:4px 0 20px 0; line-height:1.55; }
.assessment-columns { display:grid; grid-template-columns: 1fr; gap:12px; min-width:0; }
.assessment-columns > div { min-width:0; overflow:hidden; }
.assessment-col-right { border-left:none; padding-left:0; }
.section-title { font-family: 'Space Grotesk', sans-serif !important; font-size: var(--assessment-header-size); font-weight: var(--assessment-header-weight); color: var(--assessment-header-color); margin-bottom:10px; padding-bottom:6px; border-bottom:1px solid #eaf0fb; line-height: 1.2; }
.kv-row { display:grid; grid-template-columns: auto 1fr; gap:6px; margin:8px 0; align-items:baseline; }
.kv-value { word-break: normal; overflow-wrap: anywhere; min-width: 0; }
.kv-label { font-size:13px; font-weight:700; color:#1e3560; }
.kv-value { font-size:13px; color:#2563eb; }
.assessment-divider { border:none; border-top:1px solid #e5edf8; margin:20px 0 16px 0; }
.scope-grid { display:grid; grid-template-columns: 1fr; gap:0; }
.sb-brand-row { display:flex; align-items:center; gap:10px; margin-bottom:10px; }
.sb-logo { width:40px; height:40px; flex-shrink:0; border-radius:10px; background:linear-gradient(160deg,#1f70cf,#1ab6a7); display:flex; align-items:center; justify-content:center; font-size:18px; }
.sb-title { font-size:22px; font-weight:800; line-height:1.1; color:#ffffff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.sb-subtitle { font-size:13px; color:#bfd4f5 !important; margin-top:4px; }
.sb-nav-item { padding:11px 12px; border-radius:12px; font-size:14px; font-weight:600; margin-bottom:8px; }
.sb-nav-item-active { background:linear-gradient(90deg,rgba(37,99,235,0.9),rgba(16,153,141,0.85)); }
.sb-system-label { margin-top:16px; font-size:12px; letter-spacing:0.06em; color:#bfd4f5 !important; font-weight:700; text-transform:uppercase; }
.sb-system-card { margin-top:10px; padding:14px; border-radius:12px; background:rgba(255,255,255,0.10); font-size:13px; line-height:1.5; }
.sb-profile { margin-top:16px; padding:12px; border-radius:12px; background:rgba(255,255,255,0.12); display:flex; align-items:center; gap:10px; }
.sb-profile-avatar { width:34px; height:34px; border-radius:17px; background:linear-gradient(160deg,#ea7fa8,#7b86f6); display:flex; align-items:center; justify-content:center; font-size:12px; font-weight:700; }
.sb-profile-name { font-size:13px; font-weight:700; }
.sb-profile-role { font-size:11px; color:#bfd4f5 !important; }
@media (min-width: 1024px) {
    section[data-testid="stSidebar"] { width: 272px !important; min-width: 272px !important; }
}
@media (min-width: 1200px) {
    .assessment-columns { grid-template-columns: 1fr 1fr; gap: 0; }
    .assessment-col-right { border-left:1px solid #e5edf8; padding-left:28px; }
    .scope-grid { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 1023px) {
    .sb-title { font-size:20px; }
    section[data-testid="stSidebar"] { width: min(86vw, 300px) !important; min-width: min(86vw, 300px) !important; }
}
</style>
""",
    unsafe_allow_html=True,
)

mock_note = '<span class="mock-badge">MOCK MODE</span>' if st.session_state.effective_use_mock_data else ""
st.sidebar.markdown(
    """
<div class="sb-brand-row">
    <div class="sb-logo">🛡️</div>
    <div>
        <div class="sb-title">Risk Assistant</div>
        <div class="sb-subtitle">Risk Assessor</div>
    </div>
</div>
"""
    + mock_note
    + """
<hr style="border:0;border-top:1px solid rgba(200,225,255,0.22);margin:10px 0;">
<div class="sb-nav-item sb-nav-item-active">🏠 &nbsp;Dashboard</div>
<div class="sb-nav-item">🔍 &nbsp;Screenings</div>
<div class="sb-nav-item">⚙️ &nbsp;Rules</div>
<div class="sb-nav-item">📋 &nbsp;Reports</div>
<div class="sb-nav-item">📁 &nbsp;Audit</div>

<div class="sb-system-label">System</div>
<div class="sb-system-card">
<b>Backend URL</b><br>
"""
    + _backend_url()
    + """<br><br>
<b>Status</b><br>
"""
    + (
        "live mode"
        if st.session_state.get("frontend_live_mode")
        else
        "mock data (API unavailable)"
        if st.session_state.effective_use_mock_data and not SETTINGS["use_mock_data"]
        else "mock data"
        if st.session_state.effective_use_mock_data
        else "live api connected"
    )
    + """<br><br>
<b>Workflow</b><br>
Evidence -> Rules -> Memo
<br><br>
<b>Kimi Key</b><br>
"""
    + ("configured" if st.session_state.get("kimi_api_key_set") else "not set")
    + """<br><br>
<b>Daytona Key</b><br>
"""
    + ("configured" if st.session_state.get("daytona_api_key_set") else "not set")
    + """
</div>

<div style="height: 22px;"></div>
<div class="sb-profile">
    <div class="sb-profile-avatar">RA</div>
    <div>
        <div class="sb-profile-name">Risk Assessor</div>
        <div class="sb-profile-role">Administrator</div>
    </div>
</div>
""",
    unsafe_allow_html=True,
)

if st.session_state.effective_use_mock_data:
    st.markdown('<div class="mock-banner">Mock mode active. Run reloads local sample report.</div>', unsafe_allow_html=True)
    if st.session_state.backend_status_message:
        st.caption(st.session_state.backend_status_message)
elif st.session_state.backend_status_message:
    st.caption(st.session_state.backend_status_message)

hero_left, hero_right = st.columns([4.2, 1.0])
with hero_left:
    st.markdown(
        """
<div class="hero" style="margin-bottom:0;">
  <div class="main-title">Risk Assistant</div>
  <div class="main-subtitle">Evidence, grounded public-source screening with rubric scoring and reviewer-ready memo output.</div>
    <div class="chip-row"><span class="chip">Bright Data</span><span class="chip">LLM Classification</span><span class="chip">Rule Engine</span><span class="chip">Memo Packaging</span></div>
</div>
""",
        unsafe_allow_html=True,
    )
with hero_right:
        st.markdown('<div class="hero hero-right"><div class="hero-shield-wrap"><div class="hero-shield">🛡</div></div></div>', unsafe_allow_html=True)

with st.container(border=True):
    c1, c2, c3, c4, c5, c6 = st.columns([1.7, 1.0, 1.0, 1.2, 1.0, 0.9])
    with c1:
        subject_name = st.text_input("Subject Name", subject.get("name", ""))
    with c2:
        default_type = _api_to_ui_subject_type(subject.get("type", "organization"))
        subject_type = st.selectbox("Subject Type", SUBJECT_TYPES, index=SUBJECT_TYPES.index(default_type) if default_type in SUBJECT_TYPES else 0)
    with c3:
        country = st.text_input("Country", subject.get("country", ""))
    with c4:
        purpose = st.selectbox("Purpose", ["Vendor Onboarding", "HNW Onboarding", "Periodic Review", "Key Person Review"])
    with c5:
        role = st.text_input("Role", subject.get("role", ""))
    with c6:
        st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
        run = st.button("Run Screening", use_container_width=True)

if run:
    # Re-check backend right before submitting to handle cases where API became unavailable
    # after initial page load.
    if not SETTINGS["use_mock_data"]:
        _resolve_data_source()

    if st.session_state.get("frontend_live_mode") or _frontend_live_configured():
        try:
            with st.spinner("Running live screening via Bright Data + Kimi..."):
                st.session_state.ui_data = _run_frontend_live_screening(
                    subject_name=subject_name,
                    subject_type=subject_type,
                    country=country,
                    purpose=purpose,
                    role=role,
                )
            st.session_state.frontend_live_mode = True
            st.session_state.effective_use_mock_data = False
            st.session_state.backend_available = False
            st.session_state.backend_status_message = "Live mode connected."
            st.session_state.last_success = "Live frontend screening complete."
            st.rerun()
        except Exception as exc:
            st.session_state.frontend_live_mode = False
            _fallback_to_mock(str(exc))
            st.session_state.ui_data = load_report_from_path(DEFAULT_DATA_PATH)
            st.session_state.last_success = "Live frontend mode failed. Loaded mock data instead."
            st.rerun()
    elif st.session_state.effective_use_mock_data:
        if _frontend_live_configured():
            st.session_state.frontend_live_mode = True
            st.rerun()
        else:
            st.session_state.ui_data = load_report_from_path(DEFAULT_DATA_PATH)
            st.session_state.last_success = "Loaded mock data. Add KIMI_API_KEY + Bright Data config for live mode."
            st.rerun()
    elif not subject_name.strip():
        st.error("Subject name is required.")
    else:
        try:
            notes = []
            if purpose:
                notes.append(f"Purpose: {purpose}")
            if role.strip():
                notes.append(f"Role: {role.strip()}")
            payload = build_screen_request(subject_name, subject_type, country, input_notes="; ".join(notes) if notes else None)
            run_id = start_screening(_backend_url(), payload)
            st.session_state.active_run_id = run_id
            st.session_state.polling = True
            st.session_state.poll_deadline = time.time() + SETTINGS["poll_timeout_seconds"]
            st.session_state.last_poll_time = 0.0
            st.session_state.clarification_pending = None
            st.rerun()
        except Exception as exc:
            _fallback_to_mock(str(exc))
            st.session_state.ui_data = load_report_from_path(DEFAULT_DATA_PATH)
            st.session_state.last_success = "Live API unavailable. Loaded mock data instead."
            st.rerun()

if st.session_state.get("clarification_pending"):
    clar = st.session_state.clarification_pending
    run_id = clar.get("run_id") or st.session_state.active_run_id
    form = clar.get("clarification_form") or {}
    candidates = form.get("candidate_entities") or []
    st.warning("Entity identity is ambiguous. Provide clarification to continue.")

    with st.form("clarify"):
        clar_country = st.text_input("Country", value=(candidates[0].get("country") if candidates else ""))
        clar_industry = st.text_input("Industry", value=(candidates[0].get("industry") if candidates else ""))
        cand_labels = [f"{c.get('name','Candidate')} ({c.get('country','unknown')})" for c in candidates]
        cand_map = {label: c for label, c in zip(cand_labels, candidates)}
        selected = st.selectbox("Candidate (optional)", ["None"] + cand_labels) if cand_labels else "None"
        notes = st.text_area("Analyst notes")
        submitted = st.form_submit_button("Submit clarification")

    if submitted and run_id:
        try:
            body = {}
            if clar_country.strip():
                body["country"] = clar_country.strip()
            if clar_industry.strip():
                body["industry"] = clar_industry.strip()
            if notes.strip():
                body["notes"] = notes.strip()
            if selected != "None":
                chosen = cand_map.get(selected)
                if chosen and chosen.get("candidate_id"):
                    body["candidate_id"] = chosen["candidate_id"]
            submit_clarification(_backend_url(), run_id, body)
            st.session_state.clarification_pending = None
            st.session_state.active_run_id = run_id
            st.session_state.polling = True
            st.session_state.poll_deadline = time.time() + SETTINGS["poll_timeout_seconds"]
            st.session_state.last_poll_time = 0.0
            st.rerun()
        except Exception as exc:
            _fallback_to_mock(str(exc))
            st.session_state.ui_data = load_report_from_path(DEFAULT_DATA_PATH)
            st.session_state.clarification_pending = None
            st.session_state.last_success = "Live API unavailable during clarification. Loaded mock data instead."
            st.rerun()

if st.session_state.get("last_success"):
    st.success(st.session_state.last_success)
    st.session_state.last_success = None

support_line = risk.get("supportSummaryLine", f"{support_summary.get('high_support_evidence_count',0)} high / {support_summary.get('medium_support_evidence_count',0)} med / {support_summary.get('low_support_evidence_count',0)} low")
rule_count = len(triggered_rules)
rule_caption = f"{rule_count} rule{'s' if rule_count != 1 else ''} triggered" if triggered_rules else "No rules triggered"
st.markdown(f"""
<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:12px;">
  <div class='metric-card'><div class='metric-top'><span class='metric-icon i-risk'>🛡️</span><div class='metric-label'>Overall Risk</div></div><div class='metric-v1'>{risk.get('riskCategory','Medium Risk')}</div><div class='metric-caption'>{assessment.get('overall_risk_level','medium').title()}</div></div>
  <div class='metric-card'><div class='metric-top'><span class='metric-icon i-evidence'>📋</span><div class='metric-label'>Evidence Support</div></div><div class='metric-v2'>{support_line}</div><div class='metric-caption'>{rule_caption}</div></div>
  <div class='metric-card'><div class='metric-top'><span class='metric-icon i-entity'>👥</span><div class='metric-label'>Entity Match</div></div><div class='metric-v3'>{entity.get('score',0)}%</div><div class='metric-caption'>{entity.get('level','High')}</div></div>
  <div class='metric-card'><div class='metric-top'><span class='metric-icon i-coverage'>📊</span><div class='metric-label'>Coverage</div></div><div class='metric-v4'>{assessment.get('coverage_assessment','moderate').title()}</div><div class='metric-caption'>{risk.get('confidenceLabel','Moderate')} confidence</div></div>
  <div class='metric-card'><div class='metric-top'><span class='metric-icon i-disposition'>✅</span><div class='metric-label'>Disposition</div></div><div class='metric-v5'>{_format_disposition(assessment.get('recommended_disposition') or risk.get('recommendation'))}</div><div class='metric-caption'>Human review required</div></div>
</div>
""", unsafe_allow_html=True)

left, right = st.columns([2.6, 1.0])
with left:
    t1, t2, t3, t4, t5, t6, t7 = st.tabs(
        [
            "Assessment",
            "Evidence",
            "Risk Flags",
            "Rubric",
            "Checklist",
            "Audit",
            "Memo",
        ]
    )

    with t1:
        metadata_pairs = [
            ("Report ID:", _fmt_value(report_metadata.get("report_id"))),
            ("Generated At:", _fmt_value(report_metadata.get("generated_at"))),
            ("Workflow Run ID:", _fmt_value(report_metadata.get("workflow_run_id"))),
            ("Agent Version:", _fmt_value(report_metadata.get("agent_version"))),
            ("Data Sources:", _fmt_value(report_metadata.get("data_sources", []))),
        ]
        subject_pairs = [
            ("Primary Name:", _fmt_value(schema_subject.get("primary_name", subject.get("name")))),
            ("Subject Type:", _fmt_value(schema_subject.get("subject_type", subject.get("type")))),
            ("Country:", _fmt_country(schema_subject.get("country", subject.get("country")))),
            ("Industry:", _fmt_value(schema_subject.get("industry"))),
            ("Aliases:", _fmt_value(schema_subject.get("aliases", []))),
            ("Known Associations:", _fmt_value(schema_subject.get("known_associations", []))),
            ("Input Notes:", _fmt_value(schema_subject.get("input_notes"))),
        ]
        scope_pairs = [
            ("Jurisdiction:", _fmt_value(screening_scope.get("jurisdictions", []))),
            ("Languages:", _fmt_value(screening_scope.get("languages", []))),
            ("Lookback Period (Years):", _fmt_value(screening_scope.get("lookback_period_years"))),
            ("Search Queries:", _fmt_value(screening_scope.get("search_queries", []))),
            ("Limitations:", _fmt_value(screening_scope.get("screening_limitations", []))),
        ]
        coverage_notes = assessment.get("coverage_notes") or risk.get("summary", "")

        st.markdown(
            f"""
            <div class="assessment-shell">
              <div class="assessment-head">
                <div class="assessment-icon">📋</div>
                <div class="assessment-title">Assessment Summary</div>
              </div>
              <div class="assessment-summary">{html.escape(assessment.get('overall_summary', risk.get('summary', '')))}</div>
              <div style='font-size:12px;color:#5f7798;margin:6px 0 14px 0;line-height:1.45;'>Coverage Notes: {html.escape(str(coverage_notes))}</div>

              <div class="assessment-columns">
                <div>
                  <div class="section-title">Report Metadata</div>
                  {_kv_rows(metadata_pairs)}
                </div>
                <div class="assessment-col-right">
                  <div class="section-title">Subject</div>
                  {_kv_rows(subject_pairs)}
                </div>
              </div>

              <div class="assessment-divider"></div>

              <div>
                <div class="section-title">Screening Scope</div>
                <div class="scope-grid">
                  {_kv_rows(scope_pairs)}
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        findings = data.get("keyFindings", [])
        finding_items = []
        for finding in findings:
            finding_items.append(
                {
                    "title": finding.get("title") or finding.get("description") or "Finding",
                    "severity": str(finding.get("severity", "Medium")).title(),
                    "category": finding.get("category", ""),
                    "description": finding.get("description", ""),
                    "confidence": finding.get("confidence", ""),
                }
            )
        for flag in risk_flags:
            finding_items.append(
                {
                    "title": flag.get("title") or flag.get("description") or "Risk Flag",
                    "severity": str(flag.get("severity", "medium")).title(),
                    "category": flag.get("category", ""),
                    "description": flag.get("description", ""),
                    "confidence": "",
                }
            )

        empty_html = "<div class='kf-empty'>No key findings available.</div>" if not finding_items else ""
        st.markdown(
            f"""
            <div class='kf-shell'>
              <div class='kf-head'>
                <span class='kf-head-icon'>⌕</span>
                <div class='kf-head-title'>Key Findings</div>
              </div>
              {empty_html}
            </div>
            """,
            unsafe_allow_html=True,
        )

        for item in finding_items:
            title = str(item.get("title", "Finding"))
            with st.expander(title):
                if item.get("severity"):
                    st.markdown(f"**Severity:** {item['severity']}")
                if item.get("category"):
                    st.markdown(f"**Category:** {item['category']}")
                if item.get("confidence") not in ("", None):
                    st.markdown(f"**Confidence:** {item['confidence']}%")
                if item.get("description"):
                    st.markdown(str(item["description"]))

    with t2:
        ev_df = pd.DataFrame(evidence_raw)
        if ev_df.empty:
            st.info("No evidence items found.")
        else:
            table_rows = []
            for _, row in ev_df.iterrows():
                ev_id = html.escape(str(row.get("evidence_id", "")))
                source_type = html.escape(str(row.get("source_type", "")))
                source_name = html.escape(str(row.get("source_name", "")))
                title = html.escape(str(row.get("title", "")))
                table_rows.append(
                    f"<tr><td>{ev_id}</td><td>{source_type}</td><td>{source_name}</td><td>{title}</td></tr>"
                )

            st.markdown(
                f"""
                <div class='ev-shell'>
                  <div class='ev-head'>
                    <div class='ev-title-wrap'>
                      <span class='ev-icon'>▦</span>
                      <span class='header-standard ev-title'>Evidence</span>
                    </div>
                    <span class='ev-viewall'>View all</span>
                  </div>
                  <div class='ev-table-wrap'>
                    <table class='ev-table'>
                      <thead>
                        <tr>
                          <th style='width:13%;'>Evidence ID</th>
                          <th style='width:13%;'>Source Type</th>
                          <th style='width:17%;'>Source</th>
                          <th>Title</th>
                        </tr>
                      </thead>
                      <tbody>
                        {''.join(table_rows)}
                      </tbody>
                    </table>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            for idx, row in ev_df.iterrows():
                ev_id = str(row.get("evidence_id", "EV"))
                source_name = str(row.get("source_name", ""))
                title = str(row.get("title", ""))
                source_type = str(row.get("source_type", ""))
                url = str(row.get("url", ""))
                publication_date = str(row.get("publication_date", ""))
                snippet = str(row.get("snippet", ""))
                risk_categories = row.get("risk_categories", [])

                with st.expander(f"{ev_id} - {source_name}"):
                    if title:
                        st.markdown(f"**Title:** {title}")
                    st.markdown(f"**Source Type:** {source_type}")
                    if publication_date:
                        st.markdown(f"**Publication Date:** {publication_date}")
                    if url:
                        st.markdown(f"**URL:** {url}")
                    if risk_categories:
                        st.markdown(f"**Risk Categories:** {', '.join(risk_categories)}")
                    if snippet:
                        st.markdown(f"**Snippet:** {snippet}")

                # Keep evidence details under EV/source dropdown only; finding titles are shown in Key Findings.

    with t3:
                rf_rows = []
                for flag in risk_flags:
                    category = str(flag.get("category", "")).replace("_", " ").title()
                    rf_rows.append(
                        "<tr>"
                        f"<td class='rf-strong'>{html.escape(str(flag.get('flag_id', '')))}</td>"
                        f"<td>{html.escape(category)}</td>"
                        f"<td><span class='rf-badge rf-badge-high'><span>●</span>{html.escape(str(flag.get('severity', '')).title())}</span></td>"
                        f"<td><span class='rf-badge rf-badge-status'>{html.escape(str(flag.get('status', '')).replace('_', '-'))}</span></td>"
                        f"<td>{html.escape(str(flag.get('title', '')))}</td>"
                        "</tr>"
                    )

                if not rf_rows:
                    rf_rows = ["<tr><td colspan='5' style='text-align:center;color:#7f8b9b;'>No risk flags were generated.</td></tr>"]

                st.markdown(
                    f"""
                    <div class='rf-shell'>
                        <div class='rf-head'>
                            <div class='rf-title-wrap'>
                                <span class='rf-icon'>⚑</span>
                                <span class='header-standard'>Risk Flags</span>
                            </div>
                            <span class='rf-viewall'>View all</span>
                        </div>
                        <div class='rf-table-wrap'>
                            <table class='rf-table'>
                                <thead>
                                    <tr>
                                        <th style='width:10%;'>Flag ID</th>
                                        <th style='width:14%;'>Category</th>
                                        <th style='width:10%;'>Severity</th>
                                        <th style='width:12%;'>Status</th>
                                        <th>Title</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {''.join(rf_rows)}
                                </tbody>
                            </table>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                method = html.escape(str(determination.get("method", "rule_based_v1")))
                high_v = support_summary.get("high_support_evidence_count", 0)
                med_v = support_summary.get("medium_support_evidence_count", 0)
                low_v = support_summary.get("low_support_evidence_count", 0)
                material_v = support_summary.get("material_category_count", 0)
                tier_v = support_summary.get("official_or_tier_1_hits", 0)

                st.markdown(
                        f"""
                        <div class='rbd-shell'>
                            <div class='rbd-head'>
                                <span class='rbd-icon'>⚖</span>
                                <span class='header-standard'>Rule-Based Determination</span>
                            </div>
                            <div class='rbd-method'>
                                <span>{method}</span>
                                <span class='rbd-copy'>⧉</span>
                            </div>
                            <div class='rbd-stats'>
                                <div class='rbd-stat'><div class='rbd-label'>High</div><div class='rbd-value rbd-high'>{high_v}</div></div>
                                <div class='rbd-stat'><div class='rbd-label'>Medium</div><div class='rbd-value rbd-medium'>{med_v}</div></div>
                                <div class='rbd-stat'><div class='rbd-label'>Low</div><div class='rbd-value rbd-low'>{low_v}</div></div>
                                <div class='rbd-stat'><div class='rbd-label'>Material</div><div class='rbd-value rbd-material'>{material_v}</div></div>
                                <div class='rbd-stat'><div class='rbd-label'>Tier 1</div><div class='rbd-value rbd-tier'>{tier_v}</div></div>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                )

                if triggered_rules:
                        rules_html = "".join(
                                [f"<div class='rule-box'>{html.escape(str(rule))}</div>" for rule in triggered_rules]
                        )
                else:
                        rules_html = "<div class='kf-empty'>No triggered rules.</div>"

                st.markdown(
                        f"""
                        <div class='trg-shell'>
                            <div class='trg-head'>
                                <span class='trg-icon'>⚡</span>
                                <span class='header-standard'>Triggered Rules</span>
                            </div>
                            {rules_html}
                        </div>
                        """,
                        unsafe_allow_html=True,
                )

    with t4:
                scales = rubric_definition.get("component_scales", {})
                scale_rows = []
                for k, v in scales.items():
                        vals = ", ".join(v) if isinstance(v, list) else str(v)
                        scale_rows.append(
                                f"<tr><td>{html.escape(str(k))}</td><td>{html.escape(vals)}</td></tr>"
                        )

                if not scale_rows:
                        scale_rows = ["<tr><td colspan='2' style='text-align:center;color:#7f8b9b;'>No component scales defined.</td></tr>"]

                support_items = "".join(
                        [f"<li>{html.escape(str(item))}</li>" for item in rubric_definition.get("support_band_rules", [])]
                ) or "<li>No support band rules.</li>"
                case_items = "".join(
                        [f"<li>{html.escape(str(item))}</li>" for item in rubric_definition.get("case_risk_rules", [])]
                ) or "<li>No case risk rules.</li>"

                st.markdown(
                    f"""<div class='rub-shell'>
<div class='rub-head'>
<span class='rub-icon'>🗎</span>
<span class='header-standard'>Rubric Definition</span>
</div>
<div class='rub-version'>Rubric Version: {html.escape(str(rubric_definition.get('rubric_version', 'N/A')))}</div>

<div class='rub-subtitle'>Component Scales</div>
<div class='rub-table-wrap'>
<table class='rub-table'>
<thead>
<tr>
<th style='width:46%;'>Component</th>
<th>Values</th>
</tr>
</thead>
<tbody>
{''.join(scale_rows)}
</tbody>
</table>
</div>

<div class='rub-rules-grid'>
<div>
<div class='rub-rule-title'>Support Band Rules</div>
<ul class='rub-rule-list'>{support_items}</ul>
</div>
<div>
<div class='rub-rule-title'>Case Risk Rules</div>
<ul class='rub-rule-list'>{case_items}</ul>
</div>
</div>
</div>""",
                    unsafe_allow_html=True,
                )

    with t5:
        st.markdown("### Analyst Checklist")
        checklist_items = analyst_checklist if isinstance(analyst_checklist, list) else []
        checklist_signature = tuple(
            f"{item.get('item_id', '')}:{item.get('status', '')}" for item in checklist_items
        )
        if st.session_state.get("checklist_signature") != checklist_signature:
            st.session_state.checklist_signature = checklist_signature
            st.session_state.checklist_done = {
                f"{item.get('item_id', '')}-{idx}": item.get("status") == "completed"
                for idx, item in enumerate(checklist_items)
            }

        if not checklist_items:
            st.info("No analyst checklist items.")
        else:
            done_count = 0
            for idx, item in enumerate(checklist_items):
                row_key = f"{item.get('item_id', 'item')}-{idx}"
                current_done = st.session_state.checklist_done.get(
                    row_key, item.get("status") == "completed"
                )

                c_done, c_action, c_meta = st.columns([0.15, 0.6, 0.25])
                with c_done:
                    done = st.checkbox(
                        "Done",
                        value=current_done,
                        key=f"checklist_done_{row_key}",
                    )
                with c_action:
                    st.write(f"**{item.get('action', 'Checklist action')}**")
                    st.caption(item.get("reason", ""))
                with c_meta:
                    st.write(f"**Priority:** {str(item.get('priority', 'medium')).title()}")
                    st.write(f"**Item ID:** {item.get('item_id', f'AC-{idx + 1}')}")

                st.session_state.checklist_done[row_key] = done
                item["status"] = "completed" if done else "pending"
                if done:
                    done_count += 1

            st.progress(done_count / max(len(checklist_items), 1))
            st.caption(f"Checklist completion: {done_count}/{len(checklist_items)} items done")

    with t6:
                def _audit_value(val):
                        if val is None:
                                return "-"
                        if isinstance(val, list):
                                if not val:
                                        return "-"
                                joined = " ".join(str(x) for x in val if str(x).strip())
                                return joined if joined.strip() else "-"
                        text = str(val).strip()
                        if text in {"", "[]"}:
                                return "-"
                        return text

                audit_rows = []
                for k, v in audit_trail_raw.items():
                        audit_rows.append(
                                f"<tr><td>{html.escape(str(k))}</td><td>{html.escape(_audit_value(v))}</td></tr>"
                        )
                if not audit_rows:
                        audit_rows = ["<tr><td colspan='2' style='text-align:center;color:#7f8b9b;'>No audit data.</td></tr>"]

                st.markdown(
                        f"""
                        <div class='aud-shell'>
                            <div class='aud-head'>
                                <span class='aud-icon'>◷</span>
                                <span class='header-standard' style='font-size:20px;'>Audit Trail</span>
                            </div>
                            <div class='aud-table-wrap'>
                                <table class='aud-table'>
                                    <thead>
                                        <tr>
                                            <th style='width:44%;'>Field</th>
                                            <th>Value</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {''.join(audit_rows)}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                )

    with t7:
                full_subject = schema_subject.get("primary_name") or subject.get("name", "-")
                full_disposition = _format_disposition(assessment.get("recommended_disposition") or risk.get("recommendation", ""))
                full_summary = assessment.get("overall_summary") or ""
                full_rationale = assessment.get("disposition_rationale") or determination.get("rationale") or ""

                st.markdown(
                        f"""
                        <div class='fm-shell'>
                            <div class='fm-head'>
                                <span class='fm-icon'>📄</span>
                                <span class='fm-title'>Full Memo</span>
                            </div>
                            <div class='fm-subject'>
                                <b>Subject:</b> <span class='fm-subject-value'>{html.escape(str(full_subject))}</span>
                            </div>
                            <div class='fm-body'>{html.escape(str(full_summary))}</div>
                            <div class='fm-disp'>
                                <div class='fm-disp-line'><b>Disposition:</b> {html.escape(str(full_disposition))}</div>
                                <div class='fm-disp-body'>{html.escape(str(full_rationale))}</div>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                )

with right:
    subject_name_display = schema_subject.get("primary_name", subject.get("name", ""))
    disposition_display = _format_disposition(assessment.get("recommended_disposition") or risk.get("recommendation", ""))
    disposition_rationale = assessment.get("disposition_rationale", determination.get("rationale", ""))
    memo_body = memo.get("body", "")
    memo_snippet = html.escape(memo_body[:300]).replace("\n", "<br>") if memo_body else ""
    workflow_run_id = st.session_state.active_run_id or report_metadata.get("workflow_run_id")
    has_real_backend_run = bool(workflow_run_id) and not str(workflow_run_id).startswith("WF-")

    st.markdown(
        f"""
<div class='panel' style='margin-bottom:10px;'>
  <div style='display:flex;align-items:center;gap:10px;margin-bottom:12px;'>
    <div style='width:36px;height:36px;border-radius:10px;background:#e8f1ff;display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0;'>📋</div>
    <div class='header-standard memo-preview-title'>Memo Preview</div>
  </div>
  <div style='font-size:13px;margin-bottom:8px;'><b>Subject:</b> {html.escape(subject_name_display)}</div>
  <div style='font-size:13px;color:#444;line-height:1.55;margin-bottom:10px;'>{memo_snippet}</div>
  <div style='font-size:13px;margin-bottom:14px;'><b>Disposition:</b> <span style='color:#0f9d8d;font-weight:700;'>{html.escape(disposition_display)}</span><br><span style='font-size:12px;color:#5f7798;'>{html.escape(disposition_rationale[:120]) if disposition_rationale else ''}</span></div>
</div>
""",
        unsafe_allow_html=True,
    )

    view_full_memo = st.button("View Full Memo", use_container_width=True)
    if view_full_memo:
        if st.session_state.get("frontend_live_mode"):
            st.session_state.show_full_memo = True
            st.session_state.memo_source = "live mode"
        elif st.session_state.effective_use_mock_data:
            st.session_state.show_full_memo = True
            st.session_state.memo_source = "mock"
        elif not has_real_backend_run:
            st.error("No completed backend run is loaded. Click Run Screening first, wait for completion, then try View Full Memo.")
        else:
            try:
                result = generate_sensenova_memo(_backend_url(), workflow_run_id)
                generated_memo = result.get("memo", "").strip()
                if not generated_memo:
                    raise RuntimeError("SenseNova returned an empty memo")
                st.session_state.ui_data["memo"]["body"] = generated_memo
                if "assessmentRaw" in st.session_state.ui_data:
                    st.session_state.ui_data["assessmentRaw"]["memo"] = generated_memo
                st.session_state.memo_source = result.get("source", "sensenova")
                st.session_state.show_full_memo = True
                st.rerun()
            except Exception as exc:
                if "Run not found" in str(exc):
                    st.error(
                        f"Run {workflow_run_id} was not found in backend. Run screening again to create a fresh backend run, then retry View Full Memo."
                    )
                    st.stop()
                if "HTTP 401" in str(exc) or "Forbidden" in str(exc):
                    st.error(
                        "SenseNova authorization failed (401 Forbidden). "
                        "Please update SENSENOVA_API_KEY in backend/.env with a key that has compatible-mode model access."
                    )
                    st.stop()
                st.error(f"Could not generate SenseNova memo: {exc}")

    if st.session_state.show_full_memo:
        with st.container(border=True):
            st.markdown("**Full Memo**")
            st.caption(f"Source: {st.session_state.memo_source}")
            st.markdown(
                memo_body
                if memo_body
                else "No memo body is available yet. Run screening to generate the final memo.")
            close_full_memo = st.button("Close Full Memo", use_container_width=True)
            if close_full_memo:
                st.session_state.show_full_memo = False
                st.rerun()

    with st.container(border=True):
        st.markdown(
            """<div style='display:flex;align-items:center;gap:10px;margin-bottom:10px;'>
  <div style='width:36px;height:36px;border-radius:10px;background:#e8f1ff;display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0;'>👤</div>
    <div class='header-standard reviewer-decision-title'>Reviewer Decision</div>
</div>""",
            unsafe_allow_html=True,
        )
        dcol1, dcol2 = st.columns([0.30, 0.70])
        with dcol1:
            st.markdown("<div style='font-size:13px;font-weight:600;color:#1e3560;padding-top:9px;'>Decision</div>", unsafe_allow_html=True)
        with dcol2:
            st.selectbox(
                "Decision",
                data.get("reviewerDecisionOptions", ["Approve", "Escalate to Compliance", "Reject"]),
                label_visibility="collapsed",
            )

        st.markdown("<div style='font-size:13px;font-weight:600;color:#1e3560;margin:6px 0 4px 0;'>Reviewer Notes</div>", unsafe_allow_html=True)
        st.text_area("Reviewer Notes", placeholder="Add reviewer notes...", label_visibility="collapsed", height=96)
        st.button("Submit Decision", use_container_width=True)

st.markdown(
    "<div style='margin-top:8px;font-size:11px;color:#0f6d53;background:#e8f9f3;border:1px solid #9edbc6;border-radius:8px;padding:7px 10px;display:inline-block;'><b>Disclaimer:</b> AI-assisted public-source screening only. Human compliance review required.</div>",
    unsafe_allow_html=True,
)
