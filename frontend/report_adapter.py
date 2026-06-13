"""Map v1 backend reports to the Streamlit UI view model."""

import json
from pathlib import Path
from typing import Any


def _risk_score(level: str) -> int:
    return {"low": 22, "medium": 55, "high": 78, "critical": 92}.get(level or "medium", 50)


def _risk_category(level: str) -> str:
    return {
        "low": "Low Risk",
        "medium": "Medium Risk",
        "high": "High Risk",
        "critical": "Critical Risk",
    }.get(level or "medium", "Medium Risk")


def _entity_match_summary(evidence: list[dict]) -> dict[str, Any]:
    scores = {"high": 90, "medium": 65, "low": 35}
    best = 0
    best_level = "low"
    rationale = "No evidence items available for entity match scoring."
    for item in evidence:
        rubric = item.get("rubric_assessment") or {}
        match = rubric.get("entity_match", "low")
        score = scores.get(match, 35)
        if score >= best:
            best = score
            best_level = match
            rationale = rubric.get("justification") or rationale
    return {"score": best, "level": best_level.title(), "rationale": rationale}


def _support_band_value(item: dict) -> str:
    band = item.get("support_band", "low")
    if isinstance(band, dict):
        return str(band.get("band", "low"))
    return str(band)


def v1_report_to_ui(report: dict) -> dict:
    """Convert backend ReputationScreeningReport JSON to UI mock shape."""
    assessment = report.get("assessment", {})
    subject_raw = report.get("subject", {})
    evidence = report.get("evidence", [])
    audit = report.get("audit_trail", {})
    flags = report.get("risk_flags", [])
    checklist = report.get("analyst_checklist", [])

    level = assessment.get("overall_risk_level", "medium")
    risk_summary = {
        "overallRiskScore": _risk_score(level),
        "riskCategory": _risk_category(level),
        "confidenceScore": min(95, 55 + len(evidence) * 2),
        "recommendation": assessment.get("recommended_disposition", "").replace("_", " ").title(),
        "summary": assessment.get("overall_summary", ""),
    }

    entity_match = _entity_match_summary(evidence)

    evidence_table: list[dict] = []
    for ev in evidence:
        rubric = ev.get("rubric_assessment") or {}
        evidence_table.append(
            {
                "id": ev.get("evidence_id"),
                "sourceName": ev.get("source_name"),
                "sourceUrl": ev.get("url"),
                "sourceTier": rubric.get("source_tier"),
                "supportBand": _support_band_value(ev),
                "severity": rubric.get("adverse_severity"),
                "corroboration": rubric.get("corroboration"),
                "sourceSnippet": ev.get("snippet"),
                "finding": ev.get("title"),
                "publicationDate": ev.get("publication_date"),
                "humanAction": "Review" if ev.get("is_adverse") else "No action required",
                "entityMatch": rubric.get("entity_match"),
                "adverseSeverity": rubric.get("adverse_severity"),
                "recency": rubric.get("recency"),
                "jurisdictionRelevance": rubric.get("jurisdiction_relevance"),
                "caseLinkage": rubric.get("case_linkage"),
                "supportRuleTriggered": ev.get("support_rule_triggered"),
            }
        )

    key_findings = []
    for flag in flags:
        key_findings.append(
            {
                "title": flag.get("title"),
                "category": flag.get("category"),
                "severity": (flag.get("severity") or "medium").title(),
                "confidence": 75,
                "description": flag.get("description"),
            }
        )
    if not key_findings and evidence:
        for ev in evidence[:3]:
            if ev.get("is_adverse"):
                rubric = ev.get("rubric_assessment") or {}
                key_findings.append(
                    {
                        "title": ev.get("title"),
                        "category": ", ".join(
                            c if isinstance(c, str) else str(c)
                            for c in (ev.get("risk_categories") or ["adverse_media"])
                        ),
                        "severity": (rubric.get("adverse_severity") or "medium").title(),
                        "confidence": 70,
                        "description": rubric.get("justification") or ev.get("snippet"),
                    }
                )

    memo_body = (
        f"Subject: {subject_raw.get('primary_name', '')}\n\n"
        f"{assessment.get('overall_summary', '')}\n\n"
        f"Disposition: {assessment.get('recommended_disposition', '').replace('_', ' ').title()}\n"
        f"{assessment.get('disposition_rationale', '')}"
    )

    recommended_steps = [
        {
            "priority": (item.get("priority") or "medium").title(),
            "action": item.get("action"),
            "reason": item.get("reason"),
        }
        for item in checklist
    ]

    ui_subject = {
        "name": subject_raw.get("primary_name", ""),
        "type": subject_raw.get("subject_type", "organization"),
        "country": subject_raw.get("country") or "",
        "screeningPurpose": subject_raw.get("input_notes") or "",
        "role": "",
    }

    audit_flat = {
        "Total Sources Reviewed": audit.get("total_sources_reviewed", 0),
        "Evidence Items Retained": audit.get("total_evidence_items_retained", 0),
        "False Positive Notes": len(audit.get("false_positive_notes", [])),
        "Processing Notes": len(audit.get("processing_notes", [])),
    }
    for i, note in enumerate(audit.get("processing_notes", [])[:5], start=1):
        audit_flat[f"Note {i}"] = note

    ui = dict(report)
    ui.update(
        {
            "subject": ui_subject,
            "riskSummary": risk_summary,
            "entityMatch": entity_match,
            "memo": {
                "body": memo_body,
                "disclaimer": "AI-assisted public-source screening only. Human compliance review required.",
            },
            "evidenceTable": evidence_table,
            "keyFindings": key_findings,
            "recommendedNextSteps": recommended_steps,
            "auditTrail": audit_flat,
            "reviewerDecisionOptions": [
                "Approve",
                "Proceed with Conditions",
                "Escalate to Compliance",
                "Reject",
            ],
        }
    )
    return ui


def normalize_ui_data(raw: dict) -> dict:
    if "riskSummary" in raw and "entityMatch" in raw and "memo" in raw:
        return raw
    if "assessment" in raw and "evidence" in raw:
        return v1_report_to_ui(raw)
    raise ValueError("Unrecognized report JSON shape")


def load_report_from_path(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"Report file not found: {path}")
    with path.open(encoding="utf-8") as f:
        raw = json.load(f)
    return normalize_ui_data(raw)
