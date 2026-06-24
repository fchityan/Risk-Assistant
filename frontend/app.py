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
from services.bright_data import bright_data_missing_fields, collect_public_data
from services.llm_reasoning import KIMI_API_KEY, analyze_with_llm
from services.sensenova import generate_memo
from settings import get_frontend_settings
from style_loader import inject_app_styles

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


def _blank_ui_data() -> dict:
    """Return an empty-but-valid UI model for live mode before a successful run."""
    ui = load_report_from_path(DEFAULT_DATA_PATH)
    ui["subject"] = {
        "name": "",
        "type": "organization",
        "country": "",
        "screeningPurpose": "",
        "role": "",
    }
    ui["riskSummary"] = {
        "riskCategory": "Not Available",
        "confidenceScore": 0,
        "recommendation": "Run Screening",
        "summary": "No live screening data loaded yet.",
        "supportSummaryLine": "0 high / 0 med / 0 low",
        "confidenceLabel": "Low",
    }
    ui["entityMatch"] = {
        "score": 0,
        "level": "Unknown",
        "rationale": "No live screening data loaded yet.",
    }
    ui["memo"] = {
        "body": "No memo available. Start a screening run to generate a report.",
        "disclaimer": "AI-assisted public-source screening only. Human compliance review required.",
    }
    ui["evidenceTable"] = []
    ui["keyFindings"] = []
    ui["recommendedNextSteps"] = []
    ui["riskFlags"] = []
    ui["evidenceRaw"] = []
    ui["assessment"] = {}
    ui["assessmentRaw"] = {}
    ui["auditTrail"] = {}
    ui["auditTrailRaw"] = {}
    ui["reportMetadata"] = {}
    return ui


def _sample_or_blank_ui_data() -> dict:
    if SETTINGS["use_mock_data"]:
        return load_report_from_path(DEFAULT_DATA_PATH)
    return _blank_ui_data()


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


def _severity_badge_class(severity: str) -> str:
    level = (severity or "").strip().lower()
    if level in {"high", "critical"}:
        return "rf-badge rf-badge-high"
    if level in {"medium", "moderate"}:
        return "rf-badge rf-badge-medium"
    return "rf-badge rf-badge-low"


def _table_empty_row(colspan: int, message: str) -> str:
    return f"<tr><td colspan='{colspan}' class='table-empty'>{html.escape(message)}</td></tr>"


def _init_state() -> None:
    if "ui_data" not in st.session_state:
        st.session_state.ui_data = _sample_or_blank_ui_data()
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


def _set_mock_mode(message: str) -> None:
    st.session_state.effective_use_mock_data = True
    st.session_state.backend_available = False
    st.session_state.frontend_live_mode = False
    st.session_state.backend_status_message = message


def _set_backend_mode(backend_url: str, health: dict) -> None:
    st.session_state.effective_use_mock_data = False
    st.session_state.backend_available = True
    st.session_state.frontend_live_mode = False
    secrets = health.get("secrets", {}) if isinstance(health, dict) else {}
    if isinstance(secrets, dict):
        st.session_state.kimi_api_key_set = bool(secrets.get("kimi"))
        st.session_state.daytona_api_key_set = bool(secrets.get("daytona"))
    st.session_state.backend_status_message = f"Connected to API at {backend_url}."


def _set_frontend_live_bypass(message: str) -> None:
    st.session_state.effective_use_mock_data = False
    st.session_state.backend_available = False
    st.session_state.frontend_live_mode = True
    st.session_state.kimi_api_key_set = True
    st.session_state.backend_status_message = message


def _resolve_data_source() -> None:
    backend_url = _backend_url()
    host = (urlparse(backend_url).hostname or "").lower()
    localhost_backend = host in {"127.0.0.1", "localhost"}

    if SETTINGS.get("use_mock_data_forced_by_cloud_localhost") and localhost_backend:
        _set_mock_mode(
            "Mock mode forced: BACKEND_URL points to localhost on Streamlit Cloud. "
            "Set BACKEND_URL to a public API URL for live screening."
        )
        return

    if SETTINGS["use_mock_data"]:
        _set_mock_mode("Mock mode forced by USE_MOCK_DATA=true.")
        return

    backend_error = "API health check did not return status=ok"
    try:
        health = get_health(backend_url)
        if health.get("status") == "ok":
            _set_backend_mode(backend_url, health)
            return
    except Exception as exc:
        backend_error = str(exc)

    if _frontend_live_configured():
        missing = bright_data_missing_fields()
        source_note = (
            " using fallback public evidence (Bright Data not configured)."
            if missing
            else " with Bright Data + Kimi."
        )
        _set_frontend_live_bypass(
            f"Backend unavailable ({backend_error}); using frontend live bypass{source_note}"
        )
        return

    _set_mock_mode(
        f"Backend unavailable ({backend_error}); loaded example profile (no live bypass keys configured)."
    )


def _fallback_to_mock(reason: str) -> None:
    _set_mock_mode(f"Live API unavailable; using example profile ({reason}).")


def _frontend_live_configured() -> bool:
    return bool((KIMI_API_KEY or "").strip())


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
    synthetic_id = f"LIVE-{int(time.time())}"
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
    ui["assessment"] = dict(ui["assessmentRaw"])
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
        st.error(f"Could not poll backend for run {run_id}: {exc}")


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

inject_app_styles()

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
<hr class="sidebar-divider">
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
        "api unavailable"
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

<div class="sidebar-spacer"></div>
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
    banner = (
        "Mock mode active. Run reloads local sample report."
        if SETTINGS["use_mock_data"]
        else "Live backend unavailable. Showing empty state instead of sample evidence."
    )
    st.markdown(f"<div class=\"mock-banner\">{banner}</div>", unsafe_allow_html=True)
    if st.session_state.backend_status_message:
        st.caption(st.session_state.backend_status_message)
elif st.session_state.backend_status_message and not st.session_state.frontend_live_mode:
    st.caption(st.session_state.backend_status_message)

hero_left, hero_right = st.columns([4.2, 1.0])
with hero_left:
    st.markdown(
        """
<div class="hero hero--flush">
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
        st.markdown('<div class="form-spacer"></div>', unsafe_allow_html=True)
        run = st.button("Run Screening", use_container_width=True)

if run:
    if not SETTINGS["use_mock_data"]:
        _resolve_data_source()

    if st.session_state.backend_available:
        if not subject_name.strip():
            st.error("Subject name is required.")
        else:
            try:
                notes = []
                if purpose:
                    notes.append(f"Purpose: {purpose}")
                if role.strip():
                    notes.append(f"Role: {role.strip()}")
                payload = build_screen_request(
                    subject_name, subject_type, country, input_notes="; ".join(notes) if notes else None
                )
                run_id = start_screening(_backend_url(), payload)
                st.session_state.active_run_id = run_id
                st.session_state.polling = True
                st.session_state.poll_deadline = time.time() + SETTINGS["poll_timeout_seconds"]
                st.session_state.last_poll_time = 0.0
                st.session_state.clarification_pending = None
                st.rerun()
            except Exception as exc:
                if _frontend_live_configured():
                    try:
                        with st.spinner("Backend unavailable; running frontend live bypass..."):
                            st.session_state.ui_data = _run_frontend_live_screening(
                                subject_name=subject_name,
                                subject_type=subject_type,
                                country=country,
                                purpose=purpose,
                                role=role,
                            )
                        _set_frontend_live_bypass(
                            f"Backend submit failed ({exc}); completed via frontend live bypass."
                        )
                        st.session_state.last_success = "Frontend live bypass screening complete."
                        st.rerun()
                    except Exception as live_exc:
                        _fallback_to_mock(str(live_exc))
                        st.session_state.ui_data = _sample_or_blank_ui_data()
                        st.session_state.last_success = "Backend and frontend live bypass failed."
                        st.rerun()
                else:
                    _fallback_to_mock(str(exc))
                    st.session_state.ui_data = _sample_or_blank_ui_data()
                    st.session_state.last_success = "Backend unavailable."
                    st.rerun()
    elif st.session_state.frontend_live_mode or _frontend_live_configured():
        try:
            with st.spinner("Running frontend live bypass (Bright Data + Kimi)..."):
                st.session_state.ui_data = _run_frontend_live_screening(
                    subject_name=subject_name,
                    subject_type=subject_type,
                    country=country,
                    purpose=purpose,
                    role=role,
                )
            _set_frontend_live_bypass("Frontend live bypass connected.")
            st.session_state.last_success = "Frontend live bypass screening complete."
            st.rerun()
        except Exception as exc:
            _fallback_to_mock(str(exc))
            st.session_state.ui_data = _sample_or_blank_ui_data()
            st.session_state.last_success = "Frontend live bypass failed."
            st.rerun()
    elif st.session_state.effective_use_mock_data:
        st.session_state.ui_data = _sample_or_blank_ui_data()
        st.session_state.last_success = "Loaded current data source."
        st.rerun()
    elif not subject_name.strip():
        st.error("Subject name is required.")
    else:
        _fallback_to_mock("No backend or live bypass path available.")
        st.session_state.ui_data = _sample_or_blank_ui_data()
        st.session_state.last_success = "No live data source available."
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
            st.error(f"Clarification submit failed: {exc}")

if st.session_state.get("last_success"):
    st.success(st.session_state.last_success)
    st.session_state.last_success = None

support_line = risk.get("supportSummaryLine", f"{support_summary.get('high_support_evidence_count',0)} high / {support_summary.get('medium_support_evidence_count',0)} med / {support_summary.get('low_support_evidence_count',0)} low")
rule_count = len(triggered_rules)
rule_caption = f"{rule_count} rule{'s' if rule_count != 1 else ''} triggered" if triggered_rules else "No rules triggered"
st.markdown(f"""
<div class="metric-grid">
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
              <div class="coverage-notes">Coverage Notes: {html.escape(str(coverage_notes))}</div>

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
        if not finding_items:
            # Fallback for inputs that provide only risk flags and no normalized key findings.
            for flag in risk_flags:
                finding_items.append(
                    {
                        "title": flag.get("title") or flag.get("description") or "Risk Flag",
                        "severity": str(flag.get("severity", "medium")).title(),
                        "category": flag.get("category", ""),
                        "description": flag.get("description", ""),
                        "confidence": flag.get("confidence", 70),
                    }
                )

        empty_html = "<div class='kf-empty'>No key findings available.</div>" if not finding_items else ""
        st.markdown(
            f"""
            <div class='kf-shell'>
              <div class='kf-head'>
                <div class='kf-title-wrap'>
                  <span class='kf-head-icon'>⌕</span>
                  <span class='header-standard'>Key Findings</span>
                </div>
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
        if st.session_state.effective_use_mock_data:
            st.warning(
                "Showing sample evidence from docs/examples/example-profile.json because live backend data is unavailable."
            )
        elif st.session_state.get("frontend_live_mode"):
            st.info("Showing frontend live bypass evidence (Bright Data + Kimi via Streamlit).")
        else:
            sources = report_metadata.get("data_sources", [])
            if sources:
                st.caption(f"Evidence source: {', '.join(str(s) for s in sources)}")

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
                      <span class='header-standard'>Evidence</span>
                    </div>
                    <span class='ev-viewall'>View all</span>
                  </div>
                  <div class='ev-table-wrap'>
                    <table class='ev-table'>
                      <thead>
                        <tr>
                          <th class='col-w-13'>Evidence ID</th>
                          <th class='col-w-13'>Source Type</th>
                          <th class='col-w-17'>Source</th>
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
                    severity = str(flag.get("severity", ""))
                    badge_class = _severity_badge_class(severity)
                    rf_rows.append(
                        "<tr>"
                        f"<td class='rf-strong'>{html.escape(str(flag.get('flag_id', '')))}</td>"
                        f"<td>{html.escape(category)}</td>"
                        f"<td><span class='{badge_class}'><span>●</span>{html.escape(severity.title())}</span></td>"
                        f"<td><span class='rf-badge rf-badge-status'>{html.escape(str(flag.get('status', '')).replace('_', '-'))}</span></td>"
                        f"<td>{html.escape(str(flag.get('title', '')))}</td>"
                        "</tr>"
                    )

                if not rf_rows:
                    rf_rows = [_table_empty_row(5, "No risk flags were generated.")]

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
                                        <th>Flag ID</th>
                                        <th>Category</th>
                                        <th>Severity</th>
                                        <th>Status</th>
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
                        scale_rows = [_table_empty_row(2, "No component scales defined.")]

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

<div class='section-title'>Component Scales</div>
<div class='rub-table-wrap'>
<table class='rub-table'>
<thead>
<tr>
<th class='col-w-46'>Component</th>
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
        st.markdown(
            """
            <div class="checklist-shell">
              <div class="kf-head">
                <div class="kf-title-wrap">
                  <span class="kf-head-icon">✓</span>
                  <span class="header-standard">Analyst Checklist</span>
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
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
                        audit_rows = [_table_empty_row(2, "No audit data.")]

                st.markdown(
                        f"""
                        <div class='aud-shell'>
                            <div class='aud-head'>
                                <span class='aud-icon'>◷</span>
                                <span class='header-standard'>Audit Trail</span>
                            </div>
                            <div class='aud-table-wrap'>
                                <table class='aud-table'>
                                    <thead>
                                        <tr>
                                            <th class='col-w-44'>Field</th>
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
                full_rationale = assessment.get("disposition_rationale") or determination.get("disposition_rationale") or ""

                st.markdown(
                        f"""
                        <div class='fm-shell'>
                            <div class='fm-head'>
                                <span class='fm-icon'>📄</span>
                                <span class='header-standard'>Full Memo</span>
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
    disposition_rationale = assessment.get("disposition_rationale", "")
    memo_body = memo.get("body", "")
    memo_snippet = html.escape(memo_body[:300]).replace("\n", "<br>") if memo_body else ""
    workflow_run_id = st.session_state.active_run_id or report_metadata.get("workflow_run_id")
    has_real_backend_run = bool(workflow_run_id) and not str(workflow_run_id).startswith(("WF-", "LIVE-"))

    st.markdown(
        f"""
<div class='panel panel--stacked'>
  <div class='panel-head-row'>
    <div class='panel-icon-lg'>📋</div>
    <div class='header-standard memo-preview-title'>Memo Preview</div>
  </div>
  <div class='memo-preview-subject'><b>Subject:</b> {html.escape(subject_name_display)}</div>
  <div class='memo-preview-body'>{memo_snippet}</div>
  <div class='memo-preview-disposition'><b>Disposition:</b> <span class='disposition-accent'>{html.escape(disposition_display)}</span><br><span class='disposition-rationale'>{html.escape(disposition_rationale[:120]) if disposition_rationale else ''}</span></div>
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
            """<div class='panel-head-row'>
  <div class='panel-icon-lg'>👤</div>
  <div class='header-standard reviewer-decision-title'>Reviewer Decision</div>
</div>""",
            unsafe_allow_html=True,
        )
        dcol1, dcol2 = st.columns([0.30, 0.70])
        with dcol1:
            st.markdown('<div class="reviewer-label reviewer-label--inline">Decision</div>', unsafe_allow_html=True)
        with dcol2:
            st.selectbox(
                "Decision",
                data.get("reviewerDecisionOptions", ["Approve", "Escalate to Compliance", "Reject"]),
                label_visibility="collapsed",
            )

        st.markdown('<div class="reviewer-label reviewer-label--block">Reviewer Notes</div>', unsafe_allow_html=True)
        st.text_area("Reviewer Notes", placeholder="Add reviewer notes...", label_visibility="collapsed", height=96)
        st.button("Submit Decision", use_container_width=True)

st.markdown(
    "<div class='disclaimer-bar'><b>Disclaimer:</b> AI-assisted public-source screening only. Human compliance review required.</div>",
    unsafe_allow_html=True,
)
