import json
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="AI Due Diligence Agent",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

with open("mock_data/mock_data.json", "r") as f:
    data = json.load(f)

risk = data["riskSummary"]
entity = data["entityMatch"]
memo = data["memo"]

st.markdown("""
<style>
    /* Hide Streamlit header, menu, deploy button, footer */
    header[data-testid="stHeader"] {
        display: none !important;
    }

    #MainMenu {
        visibility: hidden !important;
    }

    footer {
        visibility: hidden !important;
    }

    /* Hide sidebar collapse controls */
    [data-testid="collapsedControl"] {
        display: none !important;
    }

    [data-testid="stSidebarCollapseButton"] {
        display: none !important;
    }

    section[data-testid="stSidebar"] button {
        display: none !important;
    }

    section[data-testid="stSidebar"] [role="button"] {
        display: none !important;
    }

    section[data-testid="stSidebar"] svg {
        display: none !important;
    }

    .stApp {
        background-color: #f5f7fb;
    }

    /* Fixed sidebar */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #061a3a 0%, #082452 100%) !important;
        min-width: 250px !important;
        max-width: 250px !important;
        width: 250px !important;
    }

    section[data-testid="stSidebar"] > div {
        width: 250px !important;
    }

    section[data-testid="stSidebar"] * {
        color: white !important;
    }

    section[data-testid="stSidebar"] .block-container {
        padding-top: 1.4rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }

    .block-container {
        padding-top: 1.2rem !important;
        padding-left: 1.4rem !important;
        padding-right: 1.4rem !important;
        padding-bottom: 1rem !important;
        max-width: 1480px !important;
    }

    /* Sidebar */
    .sidebar-logo {
        font-size: 23px;
        font-weight: 900;
        margin-bottom: 2px;
    }

    .sidebar-subtitle {
        font-size: 12px;
        color: #b8c7e0 !important;
        margin-bottom: 22px;
    }

    .sidebar-divider {
        height: 1px;
        background: rgba(255,255,255,0.14);
        margin: 18px 0;
    }

    .sidebar-item {
        padding: 10px 12px;
        border-radius: 9px;
        margin-bottom: 7px;
        font-size: 14px;
        color: #e5eefc !important;
    }

    .sidebar-item-active {
        background-color: #2563eb;
        font-weight: 700;
    }

    .sidebar-status {
        background-color: rgba(255,255,255,0.08);
        padding: 13px;
        border-radius: 11px;
        margin-top: 28px;
        font-size: 12px;
        line-height: 1.45;
    }

    .sidebar-user {
        margin-top: 24px;
        padding-top: 15px;
        border-top: 1px solid rgba(255,255,255,0.12);
        font-size: 12px;
    }

    /* Header */
    .main-title {
        font-size: 29px;
        font-weight: 850;
        color: #111827;
        margin-bottom: 2px;
    }

    .main-subtitle {
        font-size: 13.5px;
        color: #4b5563;
        margin-bottom: 12px;
    }

    /* Compact input card */
    .input-panel {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 13px;
        padding: 12px 14px 6px 14px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        margin-bottom: 12px;
    }

    /* Make input labels clearer and smaller */
    div[data-testid="stTextInput"] label,
    div[data-testid="stSelectbox"] label,
    div[data-testid="stTextArea"] label {
        font-size: 12px !important;
        font-weight: 700 !important;
        color: #374151 !important;
        margin-bottom: 2px !important;
    }

    /* Compact text input */
    div[data-baseweb="input"] {
        min-height: 34px !important;
        height: 34px !important;
        border-radius: 8px !important;
    }

    div[data-baseweb="input"] input {
        font-size: 13px !important;
        padding-top: 6px !important;
        padding-bottom: 6px !important;
    }

    /* Compact selectbox */
    div[data-baseweb="select"] > div {
        min-height: 34px !important;
        height: 34px !important;
        border-radius: 8px !important;
        font-size: 13px !important;
    }

    div[data-baseweb="select"] span {
        font-size: 13px !important;
    }

    /* Reduce vertical spacing inside Streamlit widgets */
    div[data-testid="stVerticalBlock"] {
        gap: 0.35rem !important;
    }

    .element-container {
        margin-bottom: 0.15rem !important;
    }

    /* Button */
    button[kind="primary"] {
        background-color: #2563eb !important;
        border-radius: 8px !important;
        height: 34px !important;
        min-height: 34px !important;
        font-weight: 750 !important;
        font-size: 13px !important;
        padding: 0 12px !important;
    }

    /* Cards */
    .workflow-card {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 13px;
        padding: 14px 18px;
        margin-bottom: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }

    .metric-card {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 13px;
        padding: 14px 16px;
        min-height: 100px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        margin-bottom: 12px;
    }

    .metric-label {
        font-size: 12.5px;
        color: #374151;
        margin-bottom: 5px;
        font-weight: 700;
    }

    .metric-value-red {
        font-size: 29px;
        font-weight: 850;
        color: #dc2626;
    }

    .metric-value-orange {
        font-size: 24px;
        font-weight: 850;
        color: #d97706;
        line-height: 1.1;
    }

    .metric-value-blue {
        font-size: 29px;
        font-weight: 850;
        color: #2563eb;
    }

    .metric-value-green {
        font-size: 29px;
        font-weight: 850;
        color: #16a34a;
    }

    .metric-caption {
        font-size: 12px;
        color: #6b7280;
        margin-top: 2px;
    }

    /* Workflow */
    .workflow-step {
        display: flex;
        align-items: center;
        gap: 10px;
        min-height: 54px;
    }

    .workflow-circle-done {
        width: 36px;
        height: 36px;
        border-radius: 50%;
        border: 3px solid #22c55e;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #16a34a;
        font-weight: 850;
        font-size: 18px;
        background: white;
    }

    .workflow-circle-progress {
        width: 36px;
        height: 36px;
        border-radius: 50%;
        background: #2563eb;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-weight: 850;
        font-size: 16px;
    }

    .workflow-title {
        font-weight: 800;
        color: #111827;
        font-size: 13.5px;
    }

    .workflow-subtitle {
        font-size: 11.5px;
        color: #6b7280;
    }

    .workflow-completed {
        font-size: 11px;
        color: #16a34a;
        font-weight: 750;
    }

    .workflow-progress {
        font-size: 11px;
        color: #2563eb;
        font-weight: 750;
    }

    /* Right memo card */
    .memo-card {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 13px;
        padding: 16px;
        min-height: 360px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        margin-bottom: 12px;
    }

    .memo-title {
        font-weight: 800;
        font-size: 14.5px;
        color: #111827;
        margin-bottom: 12px;
    }

    .memo-body {
        font-size: 12.5px;
        line-height: 1.5;
        color: #374151;
    }

    .memo-link {
        color: #2563eb;
        font-weight: 700;
        font-size: 12.5px;
    }

    .decision-card {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 13px;
        padding: 14px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }

    .disclaimer {
        background: #eff6ff;
        border: 1px solid #bfdbfe;
        color: #1e3a8a;
        padding: 10px 13px;
        border-radius: 10px;
        font-size: 12px;
        margin-top: 8px;
        line-height: 1.4;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 15px;
    }

    .stTabs [data-baseweb="tab"] {
        padding-top: 7px;
        padding-bottom: 7px;
        font-weight: 650;
        font-size: 13px;
    }

    div[data-testid="stDataFrame"] {
        border-radius: 12px;
        overflow: hidden;
    }

    h3 {
        font-size: 18px !important;
    }

    h4 {
        font-size: 15px !important;
    }

</style>
""", unsafe_allow_html=True)

# Sidebar
st.sidebar.markdown("""
<div class="sidebar-logo">🛡️ TrustLens AI</div>
<div class="sidebar-subtitle">AI Due Diligence Agent</div>

<div class="sidebar-divider"></div>

<div class="sidebar-item sidebar-item-active">🏠 Dashboard</div>
<div class="sidebar-item">🔍 Screenings</div>
<div class="sidebar-item">🛡️ Watchlists</div>
<div class="sidebar-item">📄 Reports</div>
<div class="sidebar-item">🕘 Audit Trail</div>
<div class="sidebar-item">⚙️ Settings</div>

<div class="sidebar-status">
    <b>🟢 System Status</b><br>
    <span style="color:#b8c7e0 !important;">All systems operational</span><br><br>
    <b>Last Updated</b><br>
    <span style="color:#b8c7e0 !important;">Demo environment</span>
</div>

<div class="sidebar-user">
    <b>JD&nbsp;&nbsp; Jane Doe</b><br>
    <span style="color:#b8c7e0 !important;">Compliance Analyst</span>
</div>
""", unsafe_allow_html=True)

# Header
st.markdown("""
<div class="main-title">🛡️ AI Due Diligence Agent</div>
<div class="main-subtitle">
Automated due diligence screening and risk assessment for vendor onboarding and compliance
</div>
""", unsafe_allow_html=True)

# Input card
st.markdown('<div class="input-panel">', unsafe_allow_html=True)

col1, col2, col3, col4, col5, col6 = st.columns([1.55, 1.15, 1.05, 1.45, 1.05, 1.15])

with col1:
    subject_name = st.text_input("Subject Name", data["subject"]["name"])

with col2:
    subject_type = st.selectbox(
        "Subject Type",
        ["Company", "Private Company", "Individual", "HNW Prospect", "Vendor", "Key Person"],
        index=0
    )

with col3:
    country = st.selectbox(
        "Country",
        ["Singapore", "Malaysia", "Indonesia", "Thailand", "Vietnam", "Philippines"],
        index=0
    )

with col4:
    purpose = st.selectbox(
        "Screening Purpose",
        ["Vendor Onboarding", "HNW Onboarding", "Periodic Review", "Key Person Review"],
        index=0
    )

with col5:
    role = st.selectbox(
        "Role",
        ["Director", "Vendor", "Shareholder", "Beneficial Owner", "Key Person"],
        index=0
    )

with col6:
    st.markdown("<div style='height: 21px;'></div>", unsafe_allow_html=True)
    run_screening = st.button("▶ Run", type="primary", use_container_width=True)

st.markdown('</div>', unsafe_allow_html=True)

if run_screening:
    st.success("Screening completed using mock data. Real sponsor API workflow can be connected later.")

# Workflow
st.markdown('<div class="workflow-card">', unsafe_allow_html=True)

w1, w2, w3, w4 = st.columns(4)

workflow_items = [
    ("✓", "Bright Data", "Data Collection", "Completed", "done"),
    ("✓", "Daytona", "Data Processing", "Completed", "done"),
    ("✓", "Kimi", "AI Analysis", "Completed", "done"),
    ("4", "SenseNova", "Report Generation", "In Progress", "progress"),
]

for col, item in zip([w1, w2, w3, w4], workflow_items):
    icon, title, subtitle, status, state = item
    circle_class = "workflow-circle-done" if state == "done" else "workflow-circle-progress"
    status_class = "workflow-completed" if state == "done" else "workflow-progress"

    with col:
        st.markdown(f"""
        <div class="workflow-step">
            <div class="{circle_class}">{icon}</div>
            <div>
                <div class="workflow-title">{title}</div>
                <div class="workflow-subtitle">{subtitle}</div>
                <div class="{status_class}">{status}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

# Metrics
m1, m2, m3, m4 = st.columns(4)

with m1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">🛑 Overall Risk Score</div>
        <span class="metric-value-red">{risk["overallRiskScore"]}</span>
        <span style="font-size:15px;color:#6b7280;"> /100</span>
        <div class="metric-caption">{risk["riskCategory"]}</div>
    </div>
    """, unsafe_allow_html=True)

with m2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">🚩 Risk Category</div>
        <div class="metric-value-orange">{risk["riskCategory"]}</div>
        <div class="metric-caption">Requires Review</div>
    </div>
    """, unsafe_allow_html=True)

with m3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">📊 Confidence Score</div>
        <div class="metric-value-blue">{risk["confidenceScore"]}%</div>
        <div class="metric-caption">{risk.get("confidenceLabel", "Moderate Confidence")}</div>
    </div>
    """, unsafe_allow_html=True)

with m4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">🎯 Entity Match Confidence</div>
        <div class="metric-value-green">{entity["score"]}%</div>
        <div class="metric-caption">{entity.get("level", "High")}</div>
    </div>
    """, unsafe_allow_html=True)

# Main content
left, right = st.columns([2.4, 1])

with left:
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["Profile Summary", "Evidence", "Missing Info", "Memo", "Audit Trail"]
    )

    with tab1:
        st.markdown("### Profile Summary")
        st.write(data["profileSummary"]["summary"])

        c1, c2 = st.columns(2)

        with c1:
            st.markdown("#### Known Affiliations")
            for item in data["profileSummary"]["knownAffiliations"]:
                st.write(f"- {item}")

            st.markdown("#### Identifiers Found")
            for item in data["profileSummary"]["identifiersFound"]:
                st.write(f"- {item}")

        with c2:
            st.markdown("#### Entity Match")
            st.metric("Match Score", f"{entity['score']}%")
            st.write(entity["rationale"])

            if entity["ambiguities"]:
                st.warning("Potential ambiguities found:")
                for item in entity["ambiguities"]:
                    st.write(f"- {item}")

        st.markdown("#### Key Findings")
        for finding in data["keyFindings"]:
            with st.expander(f"{finding['title']} — {finding['severity']}"):
                st.write(f"**Category:** {finding['category']}")
                st.write(f"**Confidence:** {finding['confidence']}%")
                st.write(finding["description"])

    with tab2:
        st.markdown("### Evidence Summary")

        evidence_df = pd.DataFrame(data["evidenceTable"])

        display_df = pd.DataFrame({
            "Source Type": evidence_df["sourceType"],
            "Source / Link": evidence_df["sourceUrl"],
            "Summary": evidence_df["sourceSnippet"],
            "Relevance": evidence_df["confidence"].apply(lambda x: "High" if x >= 80 else "Medium"),
            "Risk Indicator": evidence_df["severity"]
        })

        st.dataframe(display_df, use_container_width=True, hide_index=True)
        st.caption(f"Showing 1 to {len(evidence_df)} of {len(evidence_df)} results")

    with tab3:
        st.markdown("### Missing Information")

        for item in data["missingInformation"]:
            st.warning(f"**{item['item']}** — {item['status']}")
            st.write(item["recommendedAction"])

        st.markdown("### Recommended Next Steps")

        for step in data["recommendedNextSteps"]:
            st.write(f"**{step['priority']} Priority:** {step['action']}")
            st.caption(step["reason"])

    with tab4:
        st.markdown("### Full Due Diligence Memo")
        st.write(memo["body"])
        st.error(memo["disclaimer"])

    with tab5:
        st.markdown("### Audit Trail")
        audit_df = pd.DataFrame(
            [{"Field": key, "Value": value} for key, value in data["auditTrail"].items()]
        )
        st.dataframe(audit_df, use_container_width=True, hide_index=True)

with right:
    st.markdown(f"""
    <div class="memo-card">
        <div class="memo-title">📄 Due Diligence Memo Preview</div>
        <div class="memo-body">
            {memo["body"]}
        </div>
        <br>
        <span class="memo-link">View full memo →</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="decision-card">', unsafe_allow_html=True)

    decision = st.selectbox(
        "Reviewer Decision",
        data["reviewerDecisionOptions"]
    )

    reviewer_notes = st.text_area(
        "Reviewer Notes",
        placeholder="Add notes or comments..."
    )

    st.button("🔒 Submit Decision", use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("""
<div class="disclaimer">
<b>ℹ️ Disclaimer:</b> This report is AI-generated and based on data from public sources.
It is not a substitute for professional judgment. All decisions must be reviewed and approved by authorized compliance personnel.
</div>
""", unsafe_allow_html=True)
