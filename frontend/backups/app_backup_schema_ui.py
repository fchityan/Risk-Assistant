import json
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Risk Assistant",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

with open("mock_data/mock_data.json", "r") as f:
    data = json.load(f)

subject = data["subject"]
risk = data["riskSummary"]
entity = data["entityMatch"]
memo = data["memo"]
assessment = data.get("assessment", {})
determination = assessment.get("determination_basis", {})
support_summary = determination.get("support_summary", {})
triggered_rules = determination.get("triggered_rules", [])

st.markdown("""
<style>
    header[data-testid="stHeader"] { display: none !important; }
    #MainMenu { visibility: hidden !important; }
    footer { visibility: hidden !important; }

    [data-testid="collapsedControl"],
    [data-testid="stSidebarCollapseButton"] {
        display: none !important;
    }

    section[data-testid="stSidebar"] button,
    section[data-testid="stSidebar"] [role="button"],
    section[data-testid="stSidebar"] svg {
        display: none !important;
    }

    .stApp {
        background-color: #f5f7fb;
    }

    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #061a3a 0%, #082452 100%) !important;
        min-width: 220px !important;
        max-width: 220px !important;
        width: 220px !important;
    }

    section[data-testid="stSidebar"] > div {
        width: 220px !important;
    }

    section[data-testid="stSidebar"] * {
        color: white !important;
    }

    section[data-testid="stSidebar"] .block-container {
        padding-top: 1rem !important;
        padding-left: 0.8rem !important;
        padding-right: 0.8rem !important;
    }

    .block-container {
        padding-top: 0.8rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        padding-bottom: 0.7rem !important;
        max-width: 1550px !important;
    }

    .sidebar-logo {
        font-size: 20px;
        font-weight: 900;
        margin-bottom: 1px;
    }

    .sidebar-subtitle {
        font-size: 11px;
        color: #b8c7e0 !important;
        margin-bottom: 14px;
    }

    .sidebar-divider {
        height: 1px;
        background: rgba(255,255,255,0.14);
        margin: 12px 0;
    }

    .sidebar-item {
        padding: 8px 10px;
        border-radius: 8px;
        margin-bottom: 5px;
        font-size: 12.5px;
        color: #e5eefc !important;
    }

    .sidebar-item-active {
        background-color: #2563eb;
        font-weight: 700;
    }

    .sidebar-status {
        background-color: rgba(255,255,255,0.08);
        padding: 10px;
        border-radius: 10px;
        margin-top: 18px;
        font-size: 11px;
        line-height: 1.35;
    }

    .main-title {
        font-size: 24px;
        font-weight: 850;
        color: #111827;
        margin-bottom: 0px;
    }

    .main-subtitle {
        font-size: 12.5px;
        color: #4b5563;
        margin-bottom: 8px;
    }

    .input-panel {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 11px;
        padding: 8px 10px 2px 10px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.035);
        margin-bottom: 8px;
    }

    .workflow-card,
    .panel-card {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 11px;
        padding: 9px 12px;
        margin-bottom: 8px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.035);
    }

    .metric-card {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 11px;
        padding: 10px 12px;
        min-height: 78px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.035);
        margin-bottom: 8px;
    }

    .metric-label {
        font-size: 11.5px;
        color: #374151;
        margin-bottom: 3px;
        font-weight: 700;
    }

    .metric-value-red {
        font-size: 24px;
        font-weight: 850;
        color: #dc2626;
    }

    .metric-value-orange {
        font-size: 18px;
        font-weight: 850;
        color: #d97706;
        line-height: 1.05;
    }

    .metric-value-blue {
        font-size: 21px;
        font-weight: 850;
        color: #2563eb;
    }

    .metric-value-green {
        font-size: 24px;
        font-weight: 850;
        color: #16a34a;
    }

    .metric-value-purple {
        font-size: 16px;
        font-weight: 850;
        color: #7c3aed;
        line-height: 1.05;
    }

    .metric-caption {
        font-size: 10.5px;
        color: #6b7280;
        margin-top: 1px;
    }

    .rule-box {
        background: #f8fafc;
        border: 1px solid #e5e7eb;
        border-left: 3px solid #2563eb;
        border-radius: 8px;
        padding: 7px 9px;
        margin-bottom: 6px;
        font-size: 11.5px;
        color: #374151;
    }

    .memo-card {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 11px;
        padding: 12px;
        min-height: 260px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.035);
        margin-bottom: 8px;
    }

    .memo-title {
        font-weight: 800;
        font-size: 13px;
        color: #111827;
        margin-bottom: 8px;
    }

    .memo-body {
        font-size: 11.5px;
        line-height: 1.42;
        color: #374151;
    }

    .decision-card {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 11px;
        padding: 10px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.035);
    }

    .disclaimer {
        background: #eff6ff;
        border: 1px solid #bfdbfe;
        color: #1e3a8a;
        padding: 8px 10px;
        border-radius: 9px;
        font-size: 11px;
        margin-top: 6px;
        line-height: 1.3;
    }

    div[data-testid="stTextInput"] label,
    div[data-testid="stSelectbox"] label,
    div[data-testid="stTextArea"] label {
        font-size: 11px !important;
        font-weight: 700 !important;
        color: #374151 !important;
        margin-bottom: 0px !important;
    }

    div[data-baseweb="input"] {
        min-height: 30px !important;
        height: 30px !important;
        border-radius: 7px !important;
    }

    div[data-baseweb="input"] input {
        font-size: 12px !important;
        padding-top: 4px !important;
        padding-bottom: 4px !important;
    }

    div[data-baseweb="select"] > div {
        min-height: 30px !important;
        height: 30px !important;
        border-radius: 7px !important;
        font-size: 12px !important;
    }

    div[data-baseweb="select"] span {
        font-size: 12px !important;
    }

    button[kind="primary"] {
        background-color: #2563eb !important;
        border-radius: 7px !important;
        height: 30px !important;
        min-height: 30px !important;
        font-weight: 750 !important;
        font-size: 12px !important;
        padding: 0 10px !important;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        border-bottom: 1px solid #e5e7eb;
    }

    .stTabs [data-baseweb="tab"] {
        padding-top: 4px;
        padding-bottom: 4px;
        font-weight: 650;
        font-size: 12px;
    }

    div[data-testid="stDataFrame"] {
        border-radius: 10px;
        overflow: hidden;
    }

    div[data-testid="stVerticalBlock"] {
        gap: 0.25rem !important;
    }

    .element-container {
        margin-bottom: 0.1rem !important;
    }

    h3 {
        font-size: 15px !important;
        margin-bottom: 0.3rem !important;
    }

    h4 {
        font-size: 13px !important;
        margin-bottom: 0.25rem !important;
    }

    p, li, span {
        font-size: 12.5px;
    }

    /* Hide empty custom card wrappers that appear as white bars */
    .panel-card:empty,
    .memo-card:empty,
    .decision-card:empty {
        display: none !important;
        height: 0 !important;
        min-height: 0 !important;
        padding: 0 !important;
        margin: 0 !important;
        border: none !important;
        box-shadow: none !important;
    }


    /* Equal metric card alignment */
    .metric-card {
        height: 120px !important;
        min-height: 120px !important;
        max-height: 120px !important;
        padding: 12px 14px !important;
        display: flex !important;
        flex-direction: column !important;
        justify-content: flex-start !important;
        overflow: hidden !important;
    }

    .metric-label {
        min-height: 30px !important;
        height: 30px !important;
        display: flex !important;
        align-items: flex-start !important;
        line-height: 1.15 !important;
        margin-bottom: 4px !important;
    }

    .metric-value-orange,
    .metric-value-blue,
    .metric-value-green,
    .metric-value-red,
    .metric-value-purple {
        min-height: 42px !important;
        height: 42px !important;
        display: flex !important;
        align-items: center !important;
        line-height: 1.05 !important;
        overflow: hidden !important;
    }

    .metric-value-purple {
        font-size: 18px !important;
        max-width: 100% !important;
        word-break: normal !important;
    }

    .metric-caption {
        min-height: 18px !important;
        height: 18px !important;
        line-height: 1.1 !important;
        margin-top: 2px !important;
    }

    .main-title {
        letter-spacing: -0.02em !important;
    }

    .sidebar-logo {
        letter-spacing: -0.02em !important;
    }


    /* Right panel improvements */
    .right-summary-card {
        margin-top: 95px !important;
    }

    .explain-card {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 11px;
        padding: 12px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.035);
        margin-top: 10px;
    }

    .explain-title {
        font-size: 13px;
        font-weight: 800;
        color: #111827;
        margin-bottom: 10px;
    }

    .explain-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px;
    }

    .explain-mini {
        background: #f8fafc;
        border: 1px solid #e5e7eb;
        border-radius: 9px;
        padding: 9px;
        min-height: 60px;
    }

    .explain-mini-label {
        font-size: 10.5px;
        color: #6b7280;
        font-weight: 700;
        margin-bottom: 4px;
    }

    .explain-mini-value {
        font-size: 15px;
        color: #111827;
        font-weight: 850;
        line-height: 1.15;
    }

    .explain-mini-value-blue {
        color: #2563eb;
    }

    .explain-mini-value-green {
        color: #16a34a;
    }

    .explain-mini-value-orange {
        color: #d97706;
    }

    .explain-mini-value-purple {
        color: #7c3aed;
    }


    /* More spacing above report summary */
    .right-summary-card {
        margin-top: 95px !important;
    }

    /* Clean vertical explainability card */
    .explain-card {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 11px;
        padding: 12px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.035);
        margin-top: 12px;
    }

    .explain-title {
        font-size: 13px;
        font-weight: 800;
        color: #111827;
        margin-bottom: 8px;
    }

    .explain-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: #f8fafc;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 8px 10px;
        margin-bottom: 7px;
    }

    .explain-label {
        font-size: 11.5px;
        font-weight: 700;
        color: #4b5563;
    }

    .explain-value {
        font-size: 12.5px;
        font-weight: 850;
        color: #111827;
        text-align: right;
        max-width: 150px;
        word-break: break-word;
    }

    .explain-blue { color: #2563eb !important; }
    .explain-green { color: #16a34a !important; }
    .explain-orange { color: #d97706 !important; }
    .explain-purple { color: #7c3aed !important; }

    /* Done status row above tabs */
    .done-row {
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        gap: 7px;
        margin: 4px 0 8px 0;
    }

    .done-pill {
        background: #ecfdf5;
        border: 1px solid #bbf7d0;
        border-radius: 999px;
        padding: 5px 8px;
        font-size: 11px;
        font-weight: 800;
        color: #166534;
        text-align: center;
        white-space: nowrap;
    }


    /* Done checklist row above tabs */
    .done-status-row {
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        gap: 6px;
        margin: 2px 0 8px 0;
    }

    .done-status-pill {
        background: #ecfdf5;
        border: 1px solid #bbf7d0;
        color: #166534;
        border-radius: 999px;
        padding: 5px 7px;
        font-size: 10.5px;
        font-weight: 800;
        text-align: center;
        white-space: nowrap;
    }


    /* Real reviewer checkbox row */
    .review-check-title {
        font-size: 12px;
        font-weight: 800;
        color: #374151;
        margin-top: 4px;
        margin-bottom: 2px;
    }

    div[data-testid="stCheckbox"] {
        margin-top: -4px !important;
        margin-bottom: -8px !important;
    }

    div[data-testid="stCheckbox"] label {
        font-size: 11px !important;
        font-weight: 750 !important;
        color: #166534 !important;
        white-space: nowrap !important;
    }

    div[data-testid="stCheckbox"] input {
        cursor: pointer !important;
    }

</style>
""", unsafe_allow_html=True)

# Sidebar
st.sidebar.markdown("""
<div class="sidebar-logo">Risk Assistant</div>
<div class="sidebar-subtitle">Evidence-Based Compliance Agent</div>

<div class="sidebar-divider"></div>

<div class="sidebar-item sidebar-item-active">🏠 Dashboard</div>
<div class="sidebar-item">🔍 Screenings</div>
<div class="sidebar-item">⚖️ Risk Rules</div>
<div class="sidebar-item">📄 Reports</div>
<div class="sidebar-item">🕘 Audit Trail</div>
<div class="sidebar-item">⚙️ Settings</div>

<div class="sidebar-status">
    <b>🟢 System Status</b><br>
    <span style="color:#b8c7e0 !important;">Kimi + SenseNova operational</span><br><br>
    <b>Workflow</b><br>
    <span style="color:#b8c7e0 !important;">Evidence → Rules → Memo</span>
</div>
""", unsafe_allow_html=True)

# Header
st.markdown("""
<div class="main-title">🛡️ Risk Assistant</div>
<div class="main-subtitle">
Evidence-grounded public-source screening with rubric scoring, triggered rules, and AI-generated compliance memo
</div>
""", unsafe_allow_html=True)

# Input Panel
col1, col2, col3, col4, col5, col6 = st.columns([1.6, 1.0, 1.0, 1.35, 0.95, 0.85])

with col1:
    subject_name = st.text_input("Subject Name", subject.get("name", ""))

with col2:
    subject_type = st.selectbox(
        "Subject Type",
        ["Company", "Private Company", "Individual", "HNW Prospect", "Vendor", "Key Person"],
        index=0
    )

with col3:
    country = st.text_input("Country", subject.get("country", ""))

with col4:
    purpose = st.selectbox(
        "Screening Purpose",
        ["Vendor Onboarding", "HNW Onboarding", "Periodic Review", "Key Person Review"],
        index=0
    )

with col5:
    role = st.text_input("Role", subject.get("role", ""))

with col6:
    st.markdown("<div style='height: 18px;'></div>", unsafe_allow_html=True)
    run_screening = st.button("▶ Run", type="primary", use_container_width=True)


if run_screening:
    st.success("Screening completed using mock compliance data.")

# Metrics
m1, m2, m3, m4, m5 = st.columns(5)

with m1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Overall Risk</div>
        <div class="metric-value-orange">{risk.get("riskCategory", "Medium Risk")}</div>
        <div class="metric-caption">{assessment.get("overall_risk_level", "medium").title()}</div>
    </div>
    """, unsafe_allow_html=True)

with m2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Risk Score</div>
        <span class="metric-value-red">{risk.get("overallRiskScore", 0)}</span>
        <span style="font-size:13px;color:#6b7280;"> /100</span>
        <div class="metric-caption">Rule-based</div>
    </div>
    """, unsafe_allow_html=True)

with m3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Entity Match</div>
        <div class="metric-value-green">{entity.get("score", 0)}%</div>
        <div class="metric-caption">{entity.get("level", "High")}</div>
    </div>
    """, unsafe_allow_html=True)

with m4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Coverage</div>
        <div class="metric-value-blue">{assessment.get("coverage_assessment", "moderate").title()}</div>
        <div class="metric-caption">{risk.get("confidenceScore", 0)}% confidence</div>
    </div>
    """, unsafe_allow_html=True)

with m5:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Disposition</div>
        <div class="metric-value-purple">{assessment.get("recommended_disposition", risk.get("recommendation", "")).replace("_", " ").title()}</div>
        <div class="metric-caption">Human review</div>
    </div>
    """, unsafe_allow_html=True)

# Main Content
left, right = st.columns([2.55, 0.95])

with left:
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        ["Assessment", "Evidence", "Rubric", "Rules", "Memo", "Audit"]
    )

    with tab1:
        st.markdown("### Assessment Summary")
        st.write(assessment.get("overall_summary", risk.get("summary", "")))

        a1, a2 = st.columns(2)

        with a1:
            st.markdown("#### Recommendation")
            st.warning(f"**Disposition:** {assessment.get('recommended_disposition', '').replace('_', ' ').title()}")
            st.write(assessment.get("disposition_rationale", ""))

        with a2:
            st.markdown("#### Entity Match")
            st.metric("Entity Match Score", f"{entity.get('score', 0)}%")
            st.write(entity.get("rationale", ""))

        st.markdown("#### Key Findings")
        for finding in data.get("keyFindings", []):
            with st.expander(f"{finding.get('title')} — {finding.get('severity')}"):
                st.write(f"**Category:** {finding.get('category')}")
                st.write(f"**Confidence:** {finding.get('confidence')}%")
                st.write(finding.get("description"))

    with tab2:
        st.markdown("### Evidence Summary")
        evidence_df = pd.DataFrame(data.get("evidenceTable", []))

        if not evidence_df.empty:
            display_df = pd.DataFrame({
                "ID": evidence_df.get("id", ""),
                "Source": evidence_df.get("sourceName", ""),
                "Tier": evidence_df.get("sourceTier", ""),
                "Support": evidence_df.get("supportBand", ""),
                "Severity": evidence_df.get("severity", ""),
                "Corroboration": evidence_df.get("corroboration", ""),
                "Summary": evidence_df.get("sourceSnippet", "")
            })

            st.dataframe(display_df, use_container_width=True, hide_index=True)

            for _, row in evidence_df.iterrows():
                with st.expander(f"{row.get('id', 'EV')} — {row.get('finding', '')}"):
                    st.write(f"**URL:** {row.get('sourceUrl', '')}")
                    st.write(f"**Publication Date:** {row.get('publicationDate', '')}")
                    st.write(f"**Human Action:** {row.get('humanAction', '')}")
        else:
            st.info("No evidence table found.")

    with tab3:
        st.markdown("### Evidence Rubric")
        evidence_df = pd.DataFrame(data.get("evidenceTable", []))

        if not evidence_df.empty:
            for _, row in evidence_df.iterrows():
                st.markdown(f"#### {row.get('id', 'Evidence')} — {row.get('sourceName', '')}")

                r1, r2, r3, r4 = st.columns(4)

                with r1:
                    st.write(f"**Entity Match:** {row.get('entityMatch', 'N/A')}")
                    st.write(f"**Source Tier:** {row.get('sourceTier', 'N/A')}")

                with r2:
                    st.write(f"**Severity:** {row.get('adverseSeverity', 'N/A')}")
                    st.write(f"**Recency:** {row.get('recency', 'N/A')}")

                with r3:
                    st.write(f"**Jurisdiction:** {row.get('jurisdictionRelevance', 'N/A')}")
                    st.write(f"**Corroboration:** {row.get('corroboration', 'N/A')}")

                with r4:
                    st.write(f"**Case Linkage:** {row.get('caseLinkage', 'N/A')}")
                    st.write(f"**Support Rule:** {row.get('supportRuleTriggered', 'N/A')}")

        else:
            st.info("No rubric evidence found.")

    with tab4:
        st.markdown("### Rule-Based Determination")
        st.code(determination.get("method", "rule_based_v1"))

        s1, s2, s3, s4, s5 = st.columns(5)
        s1.metric("High", support_summary.get("high_support_evidence_count", 0))
        s2.metric("Medium", support_summary.get("medium_support_evidence_count", 0))
        s3.metric("Low", support_summary.get("low_support_evidence_count", 0))
        s4.metric("Material", support_summary.get("material_category_count", 0))
        s5.metric("Tier 1", support_summary.get("official_or_tier_1_hits", 0))

        st.markdown("#### Triggered Rules")
        if triggered_rules:
            for rule in triggered_rules:
                st.markdown(f"<div class='rule-box'>{rule}</div>", unsafe_allow_html=True)

        st.markdown("#### Recommended Next Steps")
        for step in data.get("recommendedNextSteps", []):
            st.write(f"**{step.get('priority')}:** {step.get('action')}")
            st.caption(step.get("reason"))

    with tab5:
        st.markdown("### Full Memo")
        st.write(memo.get("body", ""))
        st.error(memo.get("disclaimer", ""))

    with tab6:
        st.markdown("### Audit Trail")
        audit_df = pd.DataFrame(
            [{"Field": key, "Value": value} for key, value in data.get("auditTrail", {}).items()]
        )
        st.dataframe(audit_df, use_container_width=True, hide_index=True)

with right:
    st.markdown(f"""
    <div class="memo-card">
        <div class="memo-title">📄 Memo Preview</div>
        <div class="memo-body">
            {memo.get("body", "")}
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="decision-card">', unsafe_allow_html=True)

    st.markdown("#### Reviewer Decision")

    decision = st.selectbox(
        "Decision",
        data.get("reviewerDecisionOptions", ["Escalate to Compliance"])
    )

    reviewer_notes = st.text_area(
        "Reviewer Notes",
        placeholder="Add notes..."
    )

    st.button("🔒 Submit", use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="panel-card">', unsafe_allow_html=True)
    st.markdown("#### Explainability")
    st.write(f"**Method:** {determination.get('method', 'rule_based_v1')}")
    st.write(f"**Rules:** {len(triggered_rules)}")
    st.write(f"**High Evidence:** {support_summary.get('high_support_evidence_count', 0)}")
    st.write(f"**Disposition:** {assessment.get('recommended_disposition', '').replace('_', ' ').title()}")
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("""
<div class="disclaimer">
<b>ℹ️ Disclaimer:</b> AI-assisted public-source screening only. Human compliance review required.
</div>
""", unsafe_allow_html=True)
EOFcd /home/daytona/due_diligence_agent

cat > app.py <<'EOF'
import json
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Risk Assistant",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

with open("mock_data/mock_data.json", "r") as f:
    data = json.load(f)

subject = data["subject"]
risk = data["riskSummary"]
entity = data["entityMatch"]
memo = data["memo"]
assessment = data.get("assessment", {})
determination = assessment.get("determination_basis", {})
support_summary = determination.get("support_summary", {})
triggered_rules = determination.get("triggered_rules", [])

st.markdown("""
<style>
    header[data-testid="stHeader"] { display: none !important; }
    #MainMenu { visibility: hidden !important; }
    footer { visibility: hidden !important; }

    [data-testid="collapsedControl"],
    [data-testid="stSidebarCollapseButton"] {
        display: none !important;
    }

    section[data-testid="stSidebar"] button,
    section[data-testid="stSidebar"] [role="button"],
    section[data-testid="stSidebar"] svg {
        display: none !important;
    }

    .stApp {
        background-color: #f5f7fb;
    }

    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #061a3a 0%, #082452 100%) !important;
        min-width: 220px !important;
        max-width: 220px !important;
        width: 220px !important;
    }

    section[data-testid="stSidebar"] > div {
        width: 220px !important;
    }

    section[data-testid="stSidebar"] * {
        color: white !important;
    }

    section[data-testid="stSidebar"] .block-container {
        padding-top: 1rem !important;
        padding-left: 0.8rem !important;
        padding-right: 0.8rem !important;
    }

    .block-container {
        padding-top: 0.8rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        padding-bottom: 0.7rem !important;
        max-width: 1550px !important;
    }

    .sidebar-logo {
        font-size: 20px;
        font-weight: 900;
        margin-bottom: 1px;
    }

    .sidebar-subtitle {
        font-size: 11px;
        color: #b8c7e0 !important;
        margin-bottom: 14px;
    }

    .sidebar-divider {
        height: 1px;
        background: rgba(255,255,255,0.14);
        margin: 12px 0;
    }

    .sidebar-item {
        padding: 8px 10px;
        border-radius: 8px;
        margin-bottom: 5px;
        font-size: 12.5px;
        color: #e5eefc !important;
    }

    .sidebar-item-active {
        background-color: #2563eb;
        font-weight: 700;
    }

    .sidebar-status {
        background-color: rgba(255,255,255,0.08);
        padding: 10px;
        border-radius: 10px;
        margin-top: 18px;
        font-size: 11px;
        line-height: 1.35;
    }

    .main-title {
        font-size: 24px;
        font-weight: 850;
        color: #111827;
        margin-bottom: 0px;
    }

    .main-subtitle {
        font-size: 12.5px;
        color: #4b5563;
        margin-bottom: 8px;
    }

    .input-panel {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 11px;
        padding: 8px 10px 2px 10px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.035);
        margin-bottom: 8px;
    }

    .workflow-card,
    .panel-card {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 11px;
        padding: 9px 12px;
        margin-bottom: 8px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.035);
    }

    .metric-card {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 11px;
        padding: 10px 12px;
        min-height: 78px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.035);
        margin-bottom: 8px;
    }

    .metric-label {
        font-size: 11.5px;
        color: #374151;
        margin-bottom: 3px;
        font-weight: 700;
    }

    .metric-value-red {
        font-size: 24px;
        font-weight: 850;
        color: #dc2626;
    }

    .metric-value-orange {
        font-size: 18px;
        font-weight: 850;
        color: #d97706;
        line-height: 1.05;
    }

    .metric-value-blue {
        font-size: 21px;
        font-weight: 850;
        color: #2563eb;
    }

    .metric-value-green {
        font-size: 24px;
        font-weight: 850;
        color: #16a34a;
    }

    .metric-value-purple {
        font-size: 16px;
        font-weight: 850;
        color: #7c3aed;
        line-height: 1.05;
    }

    .metric-caption {
        font-size: 10.5px;
        color: #6b7280;
        margin-top: 1px;
    }

    .rule-box {
        background: #f8fafc;
        border: 1px solid #e5e7eb;
        border-left: 3px solid #2563eb;
        border-radius: 8px;
        padding: 7px 9px;
        margin-bottom: 6px;
        font-size: 11.5px;
        color: #374151;
    }

    .memo-card {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 11px;
        padding: 12px;
        min-height: 260px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.035);
        margin-bottom: 8px;
    }

    .memo-title {
        font-weight: 800;
        font-size: 13px;
        color: #111827;
        margin-bottom: 8px;
    }

    .memo-body {
        font-size: 11.5px;
        line-height: 1.42;
        color: #374151;
    }

    .decision-card {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 11px;
        padding: 10px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.035);
    }

    .disclaimer {
        background: #eff6ff;
        border: 1px solid #bfdbfe;
        color: #1e3a8a;
        padding: 8px 10px;
        border-radius: 9px;
        font-size: 11px;
        margin-top: 6px;
        line-height: 1.3;
    }

    div[data-testid="stTextInput"] label,
    div[data-testid="stSelectbox"] label,
    div[data-testid="stTextArea"] label {
        font-size: 11px !important;
        font-weight: 700 !important;
        color: #374151 !important;
        margin-bottom: 0px !important;
    }

    div[data-baseweb="input"] {
        min-height: 30px !important;
        height: 30px !important;
        border-radius: 7px !important;
    }

    div[data-baseweb="input"] input {
        font-size: 12px !important;
        padding-top: 4px !important;
        padding-bottom: 4px !important;
    }

    div[data-baseweb="select"] > div {
        min-height: 30px !important;
        height: 30px !important;
        border-radius: 7px !important;
        font-size: 12px !important;
    }

    div[data-baseweb="select"] span {
        font-size: 12px !important;
    }

    button[kind="primary"] {
        background-color: #2563eb !important;
        border-radius: 7px !important;
        height: 30px !important;
        min-height: 30px !important;
        font-weight: 750 !important;
        font-size: 12px !important;
        padding: 0 10px !important;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        border-bottom: 1px solid #e5e7eb;
    }

    .stTabs [data-baseweb="tab"] {
        padding-top: 4px;
        padding-bottom: 4px;
        font-weight: 650;
        font-size: 12px;
    }

    div[data-testid="stDataFrame"] {
        border-radius: 10px;
        overflow: hidden;
    }

    div[data-testid="stVerticalBlock"] {
        gap: 0.25rem !important;
    }

    .element-container {
        margin-bottom: 0.1rem !important;
    }

    h3 {
        font-size: 15px !important;
        margin-bottom: 0.3rem !important;
    }

    h4 {
        font-size: 13px !important;
        margin-bottom: 0.25rem !important;
    }

    p, li, span {
        font-size: 12.5px;
    }

    /* Hide empty custom card wrappers that appear as white bars */
    .panel-card:empty,
    .memo-card:empty,
    .decision-card:empty {
        display: none !important;
        height: 0 !important;
        min-height: 0 !important;
        padding: 0 !important;
        margin: 0 !important;
        border: none !important;
        box-shadow: none !important;
    }


    /* Equal metric card alignment */
    .metric-card {
        height: 120px !important;
        min-height: 120px !important;
        max-height: 120px !important;
        padding: 12px 14px !important;
        display: flex !important;
        flex-direction: column !important;
        justify-content: flex-start !important;
        overflow: hidden !important;
    }

    .metric-label {
        min-height: 30px !important;
        height: 30px !important;
        display: flex !important;
        align-items: flex-start !important;
        line-height: 1.15 !important;
        margin-bottom: 4px !important;
    }

    .metric-value-orange,
    .metric-value-blue,
    .metric-value-green,
    .metric-value-red,
    .metric-value-purple {
        min-height: 42px !important;
        height: 42px !important;
        display: flex !important;
        align-items: center !important;
        line-height: 1.05 !important;
        overflow: hidden !important;
    }

    .metric-value-purple {
        font-size: 18px !important;
        max-width: 100% !important;
        word-break: normal !important;
    }

    .metric-caption {
        min-height: 18px !important;
        height: 18px !important;
        line-height: 1.1 !important;
        margin-top: 2px !important;
    }

    .main-title {
        letter-spacing: -0.02em !important;
    }

    .sidebar-logo {
        letter-spacing: -0.02em !important;
    }


    /* Right panel improvements */
    .right-summary-card {
        margin-top: 95px !important;
    }

    .explain-card {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 11px;
        padding: 12px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.035);
        margin-top: 10px;
    }

    .explain-title {
        font-size: 13px;
        font-weight: 800;
        color: #111827;
        margin-bottom: 10px;
    }

    .explain-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px;
    }

    .explain-mini {
        background: #f8fafc;
        border: 1px solid #e5e7eb;
        border-radius: 9px;
        padding: 9px;
        min-height: 60px;
    }

    .explain-mini-label {
        font-size: 10.5px;
        color: #6b7280;
        font-weight: 700;
        margin-bottom: 4px;
    }

    .explain-mini-value {
        font-size: 15px;
        color: #111827;
        font-weight: 850;
        line-height: 1.15;
    }

    .explain-mini-value-blue {
        color: #2563eb;
    }

    .explain-mini-value-green {
        color: #16a34a;
    }

    .explain-mini-value-orange {
        color: #d97706;
    }

    .explain-mini-value-purple {
        color: #7c3aed;
    }


    /* More spacing above report summary */
    .right-summary-card {
        margin-top: 95px !important;
    }

    /* Clean vertical explainability card */
    .explain-card {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 11px;
        padding: 12px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.035);
        margin-top: 12px;
    }

    .explain-title {
        font-size: 13px;
        font-weight: 800;
        color: #111827;
        margin-bottom: 8px;
    }

    .explain-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: #f8fafc;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 8px 10px;
        margin-bottom: 7px;
    }

    .explain-label {
        font-size: 11.5px;
        font-weight: 700;
        color: #4b5563;
    }

    .explain-value {
        font-size: 12.5px;
        font-weight: 850;
        color: #111827;
        text-align: right;
        max-width: 150px;
        word-break: break-word;
    }

    .explain-blue { color: #2563eb !important; }
    .explain-green { color: #16a34a !important; }
    .explain-orange { color: #d97706 !important; }
    .explain-purple { color: #7c3aed !important; }

    /* Done status row above tabs */
    .done-row {
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        gap: 7px;
        margin: 4px 0 8px 0;
    }

    .done-pill {
        background: #ecfdf5;
        border: 1px solid #bbf7d0;
        border-radius: 999px;
        padding: 5px 8px;
        font-size: 11px;
        font-weight: 800;
        color: #166534;
        text-align: center;
        white-space: nowrap;
    }


    /* Done checklist row above tabs */
    .done-status-row {
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        gap: 6px;
        margin: 2px 0 8px 0;
    }

    .done-status-pill {
        background: #ecfdf5;
        border: 1px solid #bbf7d0;
        color: #166534;
        border-radius: 999px;
        padding: 5px 7px;
        font-size: 10.5px;
        font-weight: 800;
        text-align: center;
        white-space: nowrap;
    }


    /* Real reviewer checkbox row */
    .review-check-title {
        font-size: 12px;
        font-weight: 800;
        color: #374151;
        margin-top: 4px;
        margin-bottom: 2px;
    }

    div[data-testid="stCheckbox"] {
        margin-top: -4px !important;
        margin-bottom: -8px !important;
    }

    div[data-testid="stCheckbox"] label {
        font-size: 11px !important;
        font-weight: 750 !important;
        color: #166534 !important;
        white-space: nowrap !important;
    }

    div[data-testid="stCheckbox"] input {
        cursor: pointer !important;
    }

</style>
""", unsafe_allow_html=True)

# Sidebar
st.sidebar.markdown("""
<div class="sidebar-logo">Risk Assistant</div>
<div class="sidebar-subtitle">Evidence-Based Compliance Agent</div>

<div class="sidebar-divider"></div>

<div class="sidebar-item sidebar-item-active">🏠 Dashboard</div>
<div class="sidebar-item">🔍 Screenings</div>
<div class="sidebar-item">⚖️ Risk Rules</div>
<div class="sidebar-item">📄 Reports</div>
<div class="sidebar-item">🕘 Audit Trail</div>
<div class="sidebar-item">⚙️ Settings</div>

<div class="sidebar-status">
    <b>🟢 System Status</b><br>
    <span style="color:#b8c7e0 !important;">Kimi + SenseNova operational</span><br><br>
    <b>Workflow</b><br>
    <span style="color:#b8c7e0 !important;">Evidence → Rules → Memo</span>
</div>
""", unsafe_allow_html=True)

# Header
st.markdown("""
<div class="main-title">🛡️ Risk Assistant</div>
<div class="main-subtitle">
Evidence-grounded public-source screening with rubric scoring, triggered rules, and AI-generated compliance memo
</div>
""", unsafe_allow_html=True)

# Input Panel
col1, col2, col3, col4, col5, col6 = st.columns([1.6, 1.0, 1.0, 1.35, 0.95, 0.85])

with col1:
    subject_name = st.text_input("Subject Name", subject.get("name", ""))

with col2:
    subject_type = st.selectbox(
        "Subject Type",
        ["Company", "Private Company", "Individual", "HNW Prospect", "Vendor", "Key Person"],
        index=0
    )

with col3:
    country = st.text_input("Country", subject.get("country", ""))

with col4:
    purpose = st.selectbox(
        "Screening Purpose",
        ["Vendor Onboarding", "HNW Onboarding", "Periodic Review", "Key Person Review"],
        index=0
    )

with col5:
    role = st.text_input("Role", subject.get("role", ""))

with col6:
    st.markdown("<div style='height: 18px;'></div>", unsafe_allow_html=True)
    run_screening = st.button("▶ Run", type="primary", use_container_width=True)


if run_screening:
    st.success("Screening completed using mock compliance data.")

# Metrics
m1, m2, m3, m4, m5 = st.columns(5)

with m1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Overall Risk</div>
        <div class="metric-value-orange">{risk.get("riskCategory", "Medium Risk")}</div>
        <div class="metric-caption">{assessment.get("overall_risk_level", "medium").title()}</div>
    </div>
    """, unsafe_allow_html=True)

with m2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Risk Score</div>
        <span class="metric-value-red">{risk.get("overallRiskScore", 0)}</span>
        <span style="font-size:13px;color:#6b7280;"> /100</span>
        <div class="metric-caption">Rule-based</div>
    </div>
    """, unsafe_allow_html=True)

with m3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Entity Match</div>
        <div class="metric-value-green">{entity.get("score", 0)}%</div>
        <div class="metric-caption">{entity.get("level", "High")}</div>
    </div>
    """, unsafe_allow_html=True)

with m4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Coverage</div>
        <div class="metric-value-blue">{assessment.get("coverage_assessment", "moderate").title()}</div>
        <div class="metric-caption">{risk.get("confidenceScore", 0)}% confidence</div>
    </div>
    """, unsafe_allow_html=True)

with m5:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Disposition</div>
        <div class="metric-value-purple">{assessment.get("recommended_disposition", risk.get("recommendation", "")).replace("_", " ").title()}</div>
        <div class="metric-caption">Human review</div>
    </div>
    """, unsafe_allow_html=True)

# Main Content
left, right = st.columns([2.55, 0.95])

with left:
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        ["Assessment", "Evidence", "Rubric", "Rules", "Memo", "Audit"]
    )

    with tab1:
        st.markdown("### Assessment Summary")
        st.write(assessment.get("overall_summary", risk.get("summary", "")))

        a1, a2 = st.columns(2)

        with a1:
            st.markdown("#### Recommendation")
            st.warning(f"**Disposition:** {assessment.get('recommended_disposition', '').replace('_', ' ').title()}")
            st.write(assessment.get("disposition_rationale", ""))

        with a2:
            st.markdown("#### Entity Match")
            st.metric("Entity Match Score", f"{entity.get('score', 0)}%")
            st.write(entity.get("rationale", ""))

        st.markdown("#### Key Findings")
        for finding in data.get("keyFindings", []):
            with st.expander(f"{finding.get('title')} — {finding.get('severity')}"):
                st.write(f"**Category:** {finding.get('category')}")
                st.write(f"**Confidence:** {finding.get('confidence')}%")
                st.write(finding.get("description"))

    with tab2:
        st.markdown("### Evidence Summary")
        evidence_df = pd.DataFrame(data.get("evidenceTable", []))

        if not evidence_df.empty:
            display_df = pd.DataFrame({
                "ID": evidence_df.get("id", ""),
                "Source": evidence_df.get("sourceName", ""),
                "Tier": evidence_df.get("sourceTier", ""),
                "Support": evidence_df.get("supportBand", ""),
                "Severity": evidence_df.get("severity", ""),
                "Corroboration": evidence_df.get("corroboration", ""),
                "Summary": evidence_df.get("sourceSnippet", "")
            })

            st.dataframe(display_df, use_container_width=True, hide_index=True)

            for _, row in evidence_df.iterrows():
                with st.expander(f"{row.get('id', 'EV')} — {row.get('finding', '')}"):
                    st.write(f"**URL:** {row.get('sourceUrl', '')}")
                    st.write(f"**Publication Date:** {row.get('publicationDate', '')}")
                    st.write(f"**Human Action:** {row.get('humanAction', '')}")
        else:
            st.info("No evidence table found.")

    with tab3:
        st.markdown("### Evidence Rubric")
        evidence_df = pd.DataFrame(data.get("evidenceTable", []))

        if not evidence_df.empty:
            for _, row in evidence_df.iterrows():
                st.markdown(f"#### {row.get('id', 'Evidence')} — {row.get('sourceName', '')}")

                r1, r2, r3, r4 = st.columns(4)

                with r1:
                    st.write(f"**Entity Match:** {row.get('entityMatch', 'N/A')}")
                    st.write(f"**Source Tier:** {row.get('sourceTier', 'N/A')}")

                with r2:
                    st.write(f"**Severity:** {row.get('adverseSeverity', 'N/A')}")
                    st.write(f"**Recency:** {row.get('recency', 'N/A')}")

                with r3:
                    st.write(f"**Jurisdiction:** {row.get('jurisdictionRelevance', 'N/A')}")
                    st.write(f"**Corroboration:** {row.get('corroboration', 'N/A')}")

                with r4:
                    st.write(f"**Case Linkage:** {row.get('caseLinkage', 'N/A')}")
                    st.write(f"**Support Rule:** {row.get('supportRuleTriggered', 'N/A')}")

        else:
            st.info("No rubric evidence found.")

    with tab4:
        st.markdown("### Rule-Based Determination")
        st.code(determination.get("method", "rule_based_v1"))

        s1, s2, s3, s4, s5 = st.columns(5)
        s1.metric("High", support_summary.get("high_support_evidence_count", 0))
        s2.metric("Medium", support_summary.get("medium_support_evidence_count", 0))
        s3.metric("Low", support_summary.get("low_support_evidence_count", 0))
        s4.metric("Material", support_summary.get("material_category_count", 0))
        s5.metric("Tier 1", support_summary.get("official_or_tier_1_hits", 0))

        st.markdown("#### Triggered Rules")
        if triggered_rules:
            for rule in triggered_rules:
                st.markdown(f"<div class='rule-box'>{rule}</div>", unsafe_allow_html=True)

        st.markdown("#### Recommended Next Steps")
        for step in data.get("recommendedNextSteps", []):
            st.write(f"**{step.get('priority')}:** {step.get('action')}")
            st.caption(step.get("reason"))

    with tab5:
        st.markdown("### Full Memo")
        st.write(memo.get("body", ""))
        st.error(memo.get("disclaimer", ""))

    with tab6:
        st.markdown("### Audit Trail")
        audit_df = pd.DataFrame(
            [{"Field": key, "Value": value} for key, value in data.get("auditTrail", {}).items()]
        )
        st.dataframe(audit_df, use_container_width=True, hide_index=True)

with right:
    st.markdown(f"""
    <div class="memo-card">
        <div class="memo-title">📄 Memo Preview</div>
        <div class="memo-body">
            {memo.get("body", "")}
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="decision-card">', unsafe_allow_html=True)

    st.markdown("#### Reviewer Decision")

    decision = st.selectbox(
        "Decision",
        data.get("reviewerDecisionOptions", ["Escalate to Compliance"])
    )

    reviewer_notes = st.text_area(
        "Reviewer Notes",
        placeholder="Add notes..."
    )

    st.button("🔒 Submit", use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="panel-card">', unsafe_allow_html=True)
    st.markdown("#### Explainability")
    st.write(f"**Method:** {determination.get('method', 'rule_based_v1')}")
    st.write(f"**Rules:** {len(triggered_rules)}")
    st.write(f"**High Evidence:** {support_summary.get('high_support_evidence_count', 0)}")
    st.write(f"**Disposition:** {assessment.get('recommended_disposition', '').replace('_', ' ').title()}")
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("""
<div class="disclaimer">
<b>ℹ️ Disclaimer:</b> AI-assisted public-source screening only. Human compliance review required.
</div>
""", unsafe_allow_html=True)
