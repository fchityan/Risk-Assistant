# Business Requirements & Solution Design — Risk Assistant

This is a project-level **business-analysis and solution-design record** for a collaborative hackathon prototype, not a client-approved BRD or completed UAT certification.

## Business problem and workflow mapping

**Objective:** Help compliance and onboarding reviewers organize public-source reputational evidence, distinguish similarly named subjects, and produce reviewer-ready risk summaries with explainable rules.

**Potential stakeholders:** compliance analyst, onboarding operations owner, risk reviewer, business analyst and engineering team.

**Possible As-Is → implemented To-Be:** Manual public-source searches → structured subject intake → identity/ambiguity resolution → source collection and evidence classification → deterministic rubric-based decision rules → audit trail and review memo. Ambiguous identity cases can pause for reviewer clarification.

## Requirements Traceability Matrix

| ID | Requirement | Evidence | Suggested acceptance check |
|---|---|---|---|
| BR-01 | Distinguish the intended subject | Backend resolution stages | Trigger clarification for ambiguous identities |
| FR-01 | Preserve supporting sources and evidence | Backend screening and report schemas | Inspect evidence provenance and citations |
| FR-02 | Separate qualitative evidence from final risk decisions | LLM classification and rule stages | Verify deterministic rules determine risk/disposition |
| FR-03 | Present findings to a human reviewer | Streamlit frontend, report adapter | Inspect review dashboard and memo output |
| NFR-01 | Support reviewability and schema consistency | Pydantic / JSON Schema and audit records | Validate structured report and traceability |

These are **proposed BA acceptance checks**; no formal customer UAT is implied.

## Digital transformation considerations

Real deployment would require documented risk appetite, permitted source use, privacy and retention policies, analyst escalation, source reliability standards, failure fallback and human final-decision authority.

See [AI governance assessment](../ai-enablement/readiness-and-governance.md) and [existing architecture](../architecture.md).
