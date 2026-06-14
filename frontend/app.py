import html
import time
from pathlib import Path

import pandas as pd
import streamlit as st

from api_client import build_screen_request, get_screen_status, start_screening, submit_clarification
from report_adapter import load_report_from_path, normalize_ui_data
from settings import get_frontend_settings

st.set_page_config(
    page_title="Risk Assistant",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

FRONTEND_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_PATH = FRONTEND_DIR / "mock_data" / "mock_data.json"
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
        return ", ".join(str(v) for v in value) if value else "None"
    text = str(value).strip()
    return text if text else "None"


def _kv_rows(pairs: list[tuple[str, str]]) -> str:
    rows = []
    for label, value in pairs:
        rows.append(
            f"<div class='kv-row'><div class='kv-label'>{html.escape(label)}</div><div class='kv-value'>{html.escape(value)}</div></div>"
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


def _poll_if_needed() -> None:
    if not st.session_state.polling or SETTINGS["use_mock_data"]:
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
        status = get_screen_status(SETTINGS["backend_url"], run_id)
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
        st.error(f"Polling failed: {exc}")


_init_state()
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
.stApp { font-family: 'Manrope', sans-serif; background: linear-gradient(180deg, #f6f9ff 0%, #edf3ff 100%); }
header[data-testid="stHeader"] { display: block !important; background: transparent !important; }
button[kind="headerNoPadding"] { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; visibility: hidden !important; }
[data-testid="stSidebarCollapseButton"] { display: none !important; }
div[data-testid="stAppViewContainer"] { background: linear-gradient(180deg, #f7f9fd 0%, #f0f4fb 100%); }
h1,h2,h3,h4,h5 { font-family: 'Space Grotesk', sans-serif !important; }
section[data-testid="stSidebar"] { background: linear-gradient(190deg, #061a3a 0%, #0a2d5d 58%, #07214a 100%) !important; border-right: 1px solid rgba(180,210,255,0.25); }
section[data-testid="stSidebar"] * { color: #edf4ff !important; }
section[data-testid="stSidebar"] .block-container { padding: 16px 14px 16px 14px !important; }
.block-container { max-width: 1550px !important; padding-top: 0.85rem !important; }
.hero { border: 1px solid #d5e3fb; border-radius: 18px; padding: 16px; margin-bottom: 10px; background: radial-gradient(circle at 95% 5%, rgba(15,157,141,0.16), transparent 35%), #fff; box-shadow: 0 14px 28px rgba(24,47,82,0.06); }
.main-title { font-size: 49px; font-weight: 700; color: #1f2f5b; line-height: 1.05; margin-bottom: 4px; }
.main-subtitle { color: #36527b; font-size: 13px; margin-bottom: 6px; }
.chip { display: inline-block; font-size: 10.5px; font-weight: 700; padding: 4px 10px; margin-right: 6px; margin-bottom: 4px; border: 1px solid #cfe0fb; border-radius: 999px; background: #f7fbff; color: #2c4f80; }
.metric-card { background: #fff; border: 1px solid #d2e2fb; border-radius: 14px; padding: 10px 12px; min-height: 94px; box-shadow: 0 8px 18px rgba(24,47,82,0.07); }
.metric-top { display: flex; align-items: center; gap: 8px; margin-bottom: 3px; }
.metric-icon { width: 28px; height: 28px; border-radius: 9px; display: inline-flex; align-items: center; justify-content: center; font-size: 15px; }
.i-risk { background: #e8f0ff; color: #2f6fed; }
.i-evidence { background: #efe7ff; color: #7651ff; }
.i-entity { background: #def7ef; color: #15a173; }
.i-coverage { background: #ece9ff; color: #7355ff; }
.i-disposition { background: #def7f6; color: #119c93; }
.metric-label { font-size: 11px; color: #597294; font-weight: 700; text-transform: uppercase; }
.metric-v1 { color: #c55e31; font-size: 17px; font-weight: 800; }
.metric-v2 { color: #cc4e68; font-size: 22px; font-weight: 800; }
.metric-v3 { color: #129069; font-size: 22px; font-weight: 800; }
.metric-v4 { color: #2d6be3; font-size: 19px; font-weight: 800; }
.metric-v5 { color: #0f9d8d; font-size: 15px; font-weight: 800; }
.metric-caption { color: #5f7798; font-size: 10.5px; }
.panel { background: #fff; border: 1px solid #d6e5fb; border-radius: 14px; padding: 12px; box-shadow: 0 8px 18px rgba(24,47,82,0.08); }
.form-card { background:#ffffff; border:1px solid #d6e3f5; border-radius:12px; padding:8px 10px; box-shadow: 0 6px 14px rgba(24,47,82,0.06); margin-bottom:10px; }
.rule-box { background: #f8fbff; border: 1px solid #d8e6fc; border-left: 3px solid #2d6be3; border-radius: 8px; padding: 8px; margin-bottom: 6px; font-size: 12px; }
.mock-badge { display: inline-block; padding: 3px 8px; border-radius: 6px; font-size: 10px; font-weight: 800; color: #1f2937; background: #f59e0b; margin-bottom: 8px; }
.mock-banner { background: #fff7df; border: 1px solid #f6c25f; color: #8b5a0b; border-radius: 8px; padding: 8px 12px; margin-bottom: 8px; font-size: 12px; font-weight: 700; }
.stButton > button { border-radius: 12px !important; border: 1px solid rgba(18,132,124,0.4) !important; background: linear-gradient(90deg,#1f70cf,#119385) !important; color: #fff !important; font-weight: 700 !important; }
.stTextInput > div > div > input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div { border-radius: 12px !important; border: 1px solid #cadaf4 !important; }
.stTabs [data-baseweb="tab-list"] {
    gap: 6px;
    border-bottom: 1px solid #d7e2f4;
    padding-bottom: 0;
    margin-bottom: 10px;
}
.stTabs [data-baseweb="tab"] {
    font-size: 16px;
    font-weight: 600;
    color: #3b4d72;
    padding: 8px 8px 10px 8px;
    border-bottom: 2px solid transparent;
}
.stTabs [aria-selected="true"] {
    color: #2b406a !important;
    border-bottom: 2px solid #2f6fed !important;
}
.hero-shield-wrap { text-align: center; padding-top: 2px; }
.hero-shield { width:120px; height:120px; margin:0 auto; border-radius:50%; background:radial-gradient(circle at 40% 35%, #61a4ff, #2456d6); color:#fff; display:flex; align-items:center; justify-content:center; font-size:62px; border:4px solid #e7efff; box-shadow:0 12px 22px rgba(35,73,151,0.22); }
.panel-title { font-size: 24px; font-weight: 700; color:#1d3361; margin-bottom:8px; }
.memo-snippet { font-size:12px; color:#3e5884; line-height:1.5; max-height:120px; overflow:hidden; }
.ghost-link { border:1px solid #d4e0f6; border-radius:9px; padding:8px 10px; font-size:12px; color:#2a5ac8; background:#f8fbff; display:inline-block; }
.assessment-shell { border: 1px solid #d6e3f5; border-radius: 14px; background: #ffffff; padding: 16px; }
.assessment-head { display:flex; align-items:center; gap:10px; margin-bottom:8px; }
.assessment-icon { width:36px; height:36px; border-radius:10px; background:#e8f0ff; color:#2f6fed; display:flex; align-items:center; justify-content:center; font-size:16px; font-weight:700; }
.assessment-title { font-size:23px; font-weight:700; color:#1e315d; line-height: 1.2; }
.assessment-summary { font-size:13px; color:#2f446e; margin:6px 0 14px 0; line-height:1.45; }
.assessment-columns { display:grid; grid-template-columns: 1fr 1fr; gap:18px; }
.assessment-col-right { border-left:1px solid #dce5f5; padding-left:16px; }
.section-title { font-size:20px; font-weight:700; color:#1f315d; margin-bottom:6px; line-height:1.15; }
.kv-row { display:grid; grid-template-columns: 136px 1fr; gap:8px; margin:7px 0; }
.kv-label { font-size:13px; font-weight:700; color:#223a69; }
.kv-value { font-size:13px; color:#314c7d; }
.assessment-divider { border-top:1px solid #dce5f5; margin:14px 0 11px 0; }
.scope-grid { display:grid; grid-template-columns: 1fr 1fr; gap:18px; }
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
@media (max-width: 1023px) {
    .sb-title { font-size:20px; }
    section[data-testid="stSidebar"] { width: min(86vw, 300px) !important; min-width: min(86vw, 300px) !important; }
}
</style>
""",
    unsafe_allow_html=True,
)

mock_note = '<span class="mock-badge">MOCK MODE</span>' if SETTINGS["use_mock_data"] else ""
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
<b>Backend</b><br>
"""
    + ("mock data" if SETTINGS["use_mock_data"] else SETTINGS["backend_url"])
    + """<br><br>
<b>Workflow</b><br>
Evidence -> Rules -> Memo
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

if SETTINGS["use_mock_data"]:
    st.markdown('<div class="mock-banner">Mock mode active. Run reloads local sample report.</div>', unsafe_allow_html=True)

hero_left, hero_right = st.columns([4.2, 1.0])
with hero_left:
    st.markdown(
        """
<div class="hero" style="margin-bottom:0;">
  <div class="main-title">Risk Assistant</div>
  <div class="main-subtitle">Evidence, grounded public-source screening with rubric scoring and reviewer-ready memo output.</div>
  <span class="chip">Bright Data</span><span class="chip">LLM Classification</span><span class="chip">Rule Engine</span><span class="chip">Memo Packaging</span>
</div>
""",
        unsafe_allow_html=True,
    )
with hero_right:
    st.markdown('<div class="hero"><div class="hero-shield-wrap"><div class="hero-shield">🛡</div></div></div>', unsafe_allow_html=True)

st.markdown('<div class="form-card">', unsafe_allow_html=True)

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
    run = st.button("Run Screening", width="stretch")
st.markdown('</div>', unsafe_allow_html=True)

if run:
    if SETTINGS["use_mock_data"]:
        st.session_state.ui_data = load_report_from_path(DEFAULT_DATA_PATH)
        st.session_state.last_success = "Loaded mock data."
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
            run_id = start_screening(SETTINGS["backend_url"], payload)
            st.session_state.active_run_id = run_id
            st.session_state.polling = True
            st.session_state.poll_deadline = time.time() + SETTINGS["poll_timeout_seconds"]
            st.session_state.last_poll_time = 0.0
            st.session_state.clarification_pending = None
            st.rerun()
        except Exception as exc:
            st.error(f"Screening failed: {exc}")

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
        submit_clarification(SETTINGS["backend_url"], run_id, body)
        st.session_state.clarification_pending = None
        st.session_state.active_run_id = run_id
        st.session_state.polling = True
        st.session_state.poll_deadline = time.time() + SETTINGS["poll_timeout_seconds"]
        st.session_state.last_poll_time = 0.0
        st.rerun()

if st.session_state.get("last_success"):
    st.success(st.session_state.last_success)
    st.session_state.last_success = None

m1, m2, m3, m4, m5 = st.columns(5)
with m1:
    st.markdown(f"<div class='metric-card'><div class='metric-top'><span class='metric-icon i-risk'>◈</span><div class='metric-label'>Overall Risk</div></div><div class='metric-v1'>{risk.get('riskCategory','Medium Risk')}</div><div class='metric-caption'>{assessment.get('overall_risk_level','medium').title()}</div></div>", unsafe_allow_html=True)
with m2:
    support_line = risk.get("supportSummaryLine", f"{support_summary.get('high_support_evidence_count',0)} high / {support_summary.get('medium_support_evidence_count',0)} med / {support_summary.get('low_support_evidence_count',0)} low")
    st.markdown(f"<div class='metric-card'><div class='metric-top'><span class='metric-icon i-evidence'>▤</span><div class='metric-label'>Evidence Support</div></div><div class='metric-v2'>{support_line}</div><div class='metric-caption'>{_trunc((triggered_rules[0] if triggered_rules else 'No rules triggered'))}</div></div>", unsafe_allow_html=True)
with m3:
    st.markdown(f"<div class='metric-card'><div class='metric-top'><span class='metric-icon i-entity'>◉</span><div class='metric-label'>Entity Match</div></div><div class='metric-v3'>{entity.get('score',0)}%</div><div class='metric-caption'>{entity.get('level','High')}</div></div>", unsafe_allow_html=True)
with m4:
    st.markdown(f"<div class='metric-card'><div class='metric-top'><span class='metric-icon i-coverage'>◔</span><div class='metric-label'>Coverage</div></div><div class='metric-v4'>{assessment.get('coverage_assessment','moderate').title()}</div><div class='metric-caption'>{risk.get('confidenceLabel','Moderate')} confidence</div></div>", unsafe_allow_html=True)
with m5:
    st.markdown(f"<div class='metric-card'><div class='metric-top'><span class='metric-icon i-disposition'>✓</span><div class='metric-label'>Disposition</div></div><div class='metric-v5'>{_format_disposition(assessment.get('recommended_disposition') or risk.get('recommendation'))}</div><div class='metric-caption'>Human review required</div></div>", unsafe_allow_html=True)

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
            ("Country:", _fmt_value(schema_subject.get("country", subject.get("country")))),
            ("Industry:", _fmt_value(schema_subject.get("industry"))),
            ("Aliases:", _fmt_value(schema_subject.get("aliases", []))),
        ]
        scope_pairs = [
            ("Jurisdiction:", _fmt_value(screening_scope.get("jurisdictions", []))),
            ("Override:", "-"),
        ]

        st.markdown(
            f"""
            <div class="assessment-shell">
              <div class="assessment-head">
                <div class="assessment-icon">⎘</div>
                <div class="assessment-title">Assessment Summary</div>
              </div>
              <div class="assessment-summary">{html.escape(assessment.get('overall_summary', risk.get('summary', '')))}</div>

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

        st.markdown("### Key Findings")
        findings = data.get("keyFindings", [])
        if not findings and not risk_flags:
            st.info("No key findings available.")
        for finding in findings:
            with st.expander(f"{finding.get('title', 'Finding')} - {finding.get('severity', 'Medium')}"):
                st.write(f"**Category:** {finding.get('category', '')}")
                st.write(f"**Confidence:** {finding.get('confidence', 0)}%")
                st.write(finding.get("description", ""))
        if risk_flags:
            st.markdown("### Risk Flags")
            for flag in risk_flags:
                with st.expander(f"{flag.get('title', 'Risk Flag')} - {str(flag.get('severity', 'medium')).title()}"):
                    st.write(f"**Category:** {flag.get('category', 'other')}")
                    st.write(f"**Status:** {flag.get('status', 'open')}")
                    st.write(f"**Evidence IDs:** {', '.join(flag.get('evidence_ids', []))}")
                    st.write(flag.get("description", ""))

    with t2:
        st.markdown("### Evidence")
        ev_df = pd.DataFrame(evidence_raw)
        if ev_df.empty:
            st.info("No evidence items found.")
        else:
            st.dataframe(
                pd.DataFrame(
                    {
                        "Evidence ID": ev_df.get("evidence_id", ""),
                        "Source Type": ev_df.get("source_type", ""),
                        "Source": ev_df.get("source_name", ""),
                        "Title": ev_df.get("title", ""),
                        "Support Band": ev_df.get("support_band", ""),
                        "Adverse": ev_df.get("is_adverse", ""),
                    }
                ),
                width="stretch",
                hide_index=True,
            )

            for _, row in ev_df.iterrows():
                rubric = row.get("rubric_assessment") or {}
                with st.expander(f"{row.get('evidence_id', 'EV')} - {row.get('source_name', '')}"):
                    st.write(f"**URL:** {row.get('url', '')}")
                    st.write(f"**Publication Date:** {row.get('publication_date', '')}")
                    st.write(f"**Risk Categories:** {', '.join(row.get('risk_categories', []))}")
                    st.write(f"**Snippet:** {row.get('snippet', '')}")
                    st.write("**Rubric Assessment**")
                    st.json(rubric)

    with t3:
        st.markdown("### Risk Flags")
        if risk_flags:
            flags_df = pd.DataFrame(
                [
                    {
                        "Flag ID": f.get("flag_id", ""),
                        "Category": f.get("category", ""),
                        "Severity": f.get("severity", ""),
                        "Status": f.get("status", ""),
                        "Title": f.get("title", ""),
                    }
                    for f in risk_flags
                ]
            )
            st.dataframe(flags_df, width="stretch", hide_index=True)
        else:
            st.info("No risk flags were generated.")

        st.markdown("### Rule-Based Determination")
        st.code(determination.get("method", "rule_based_v1"))
        s1, s2, s3, s4, s5 = st.columns(5)
        s1.metric("High", support_summary.get("high_support_evidence_count", 0))
        s2.metric("Medium", support_summary.get("medium_support_evidence_count", 0))
        s3.metric("Low", support_summary.get("low_support_evidence_count", 0))
        s4.metric("Material", support_summary.get("material_category_count", 0))
        s5.metric("Tier 1", support_summary.get("official_or_tier_1_hits", 0))

        st.markdown("### Triggered Rules")
        if triggered_rules:
            for rule in triggered_rules:
                st.markdown(f"<div class='rule-box'>{html.escape(str(rule))}</div>", unsafe_allow_html=True)
        else:
            st.info("No triggered rules.")

    with t4:
        st.markdown("### Rubric Definition")
        st.write(f"**Rubric Version:** {rubric_definition.get('rubric_version', 'N/A')}")
        scales = rubric_definition.get("component_scales", {})
        if scales:
            st.markdown("#### Component Scales")
            scale_df = pd.DataFrame(
                [{"Component": k, "Values": ", ".join(v)} for k, v in scales.items()]
            )
            st.dataframe(scale_df, width="stretch", hide_index=True)
        st.markdown("#### Support Band Rules")
        for item in rubric_definition.get("support_band_rules", []):
            st.write(f"- {item}")
        st.markdown("#### Case Risk Rules")
        for item in rubric_definition.get("case_risk_rules", []):
            st.write(f"- {item}")

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
        st.markdown("### Audit Trail")
        audit_df = pd.DataFrame([{"Field": str(k), "Value": str(v)} for k, v in audit_trail_raw.items()])
        st.dataframe(audit_df, width="stretch", hide_index=True)

    with t7:
        st.markdown("### Full Memo")
        st.write(assessment.get("memo") or memo.get("body", ""))

with right:
    st.markdown(
        f"<div class='panel'><div class='panel-title'>Memo Preview</div><div class='memo-snippet'>{html.escape(memo.get('body', '')).replace(chr(10), '<br>')}</div><div style='margin-top:10px;'><span class='ghost-link'>View Full Memo ↗</span></div></div>",
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    st.markdown("<div class='panel'>", unsafe_allow_html=True)
    st.markdown("#### Reviewer Decision")
    st.selectbox("Decision", data.get("reviewerDecisionOptions", ["Escalate to Compliance"]))
    st.text_area("Reviewer Notes", placeholder="Add reviewer notes...")
    st.button("Submit Decision", width="stretch")
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown(
    "<div style='margin-top:8px;font-size:11px;color:#0f6d53;background:#e8f9f3;border:1px solid #9edbc6;border-radius:8px;padding:7px 10px;display:inline-block;'><b>Disclaimer:</b> AI-assisted public-source screening only. Human compliance review required.</div>",
    unsafe_allow_html=True,
)
