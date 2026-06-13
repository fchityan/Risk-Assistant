"""Stage 5: Deterministic rule engine and final report assembly."""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from config import get_settings
from schemas.report import (
    AnalystChecklistItem,
    Assessment,
    AuditTrail,
    ComponentScales,
    DeterminationBasis,
    EvidenceItem,
    EvidenceClassification,
    ReportMetadata,
    ReputationScreeningReport,
    RiskFlag,
    RubricAssessment,
    RubricDefinition,
    ScreeningScope,
    Subject,
    SupportSummary,
)
from schemas.rubric import (
    AdverseSeverity,
    ChecklistPriority,
    Corroboration,
    CoverageAssessment,
    DataSource,
    DeterminationMethod,
    EntityMatch,
    EvidenceSourceType,
    OverallRiskLevel,
    RecommendedDisposition,
    Recency,
    RiskCategory,
    SourceTier,
    SupportBand,
)

RULES_PATH = Path(__file__).resolve().parent.parent / "config" / "rules_v1.json"


@dataclass
class RubricItem:
    evidence_id: str
    entity_match: str
    source_tier: str
    adverse_severity: str
    recency: str
    jurisdiction_relevance: str
    corroboration: str
    case_linkage: str
    risk_categories: list[str]


def load_rules_config() -> dict:
    with open(RULES_PATH, encoding="utf-8") as f:
        return json.load(f)


def compute_support_band(r: RubricItem) -> tuple[str, str]:
    if (
        r.entity_match == "high"
        and r.source_tier in ("tier_1", "tier_2")
        and r.adverse_severity in ("high", "critical")
        and r.case_linkage == "high"
        and (r.recency == "current" or r.corroboration == "multi_source")
    ):
        return "high", "EVIDENCE_HIGH_01"

    if (
        r.entity_match in ("medium", "high")
        and r.source_tier == "tier_1"
        and r.adverse_severity in ("high", "critical")
        and r.case_linkage in ("medium", "high")
    ):
        return "high", "EVIDENCE_HIGH_02"

    medium_hits = sum(
        [
            r.source_tier in ("tier_1", "tier_2"),
            r.recency in ("recent", "current"),
            r.jurisdiction_relevance in ("medium", "high"),
            r.corroboration in ("single_source", "multi_source"),
            r.case_linkage in ("medium", "high"),
        ]
    )
    if (
        r.entity_match in ("medium", "high")
        and r.adverse_severity in ("medium", "high", "critical")
        and medium_hits >= 2
    ):
        return "medium", "EVIDENCE_MEDIUM_01"

    return "low", "EVIDENCE_LOW_01"


def compute_case_risk(
    evidence_items: list[dict],
    rubric_items: list[RubricItem],
    support_bands: dict[str, str],
    rules_config: dict,
) -> dict:
    material_categories = set(rules_config.get("material_categories", []))

    high_count = sum(1 for v in support_bands.values() if v == "high")
    medium_count = sum(1 for v in support_bands.values() if v == "medium")
    low_count = sum(1 for v in support_bands.values() if v == "low")
    tier1_hits = sum(
        1
        for r in rubric_items
        if r.source_tier == "tier_1"
        and support_bands.get(r.evidence_id) in ("high", "medium")
    )
    critical_hits = sum(1 for r in rubric_items if r.adverse_severity == "critical")

    material_category_count = len(
        {
            cat
            for item in evidence_items
            for cat in item.get("risk_categories", [])
            if cat in material_categories
            and support_bands.get(item["evidence_id"]) in ("medium", "high")
        }
    )

    triggered_rules: list[str] = []
    overall_risk = "low"
    disposition = "no_material_concern"

    if critical_hits >= 1 and high_count >= 1:
        overall_risk = "high"
        disposition = "reject_or_hold"
        triggered_rules.append(
            "CASE_HIGH_01: critical adverse signal with high-support evidence"
        )
    elif high_count >= 2 and material_category_count >= 1:
        overall_risk = "high"
        disposition = "reject_or_hold"
        triggered_rules.append(
            "CASE_HIGH_02: two+ high-support items in material categories"
        )
    elif tier1_hits >= 1 and high_count >= 1:
        overall_risk = "high"
        disposition = "reject_or_hold"
        triggered_rules.append("CASE_HIGH_03: tier-1 source high-support finding")
    elif (high_count >= 1 or medium_count >= 2) and material_category_count >= 1:
        overall_risk = "medium"
        disposition = "escalate_to_compliance"
        triggered_rules.append(
            "CASE_MEDIUM_01: medium/high-support finding in material category"
        )
    elif medium_count >= 1:
        overall_risk = "medium"
        disposition = "manual_review_recommended"
        triggered_rules.append("CASE_MEDIUM_02: medium-support finding warrants review")
    else:
        triggered_rules.append(
            "CASE_LOW_01: no material adverse findings above low-support threshold"
        )

    return {
        "overall_risk_level": overall_risk,
        "recommended_disposition": disposition,
        "determination_basis": {
            "method": "rule_based_v1",
            "support_summary": {
                "high_support_evidence_count": high_count,
                "medium_support_evidence_count": medium_count,
                "low_support_evidence_count": low_count,
                "material_category_count": material_category_count,
                "official_or_tier_1_hits": tier1_hits,
            },
            "triggered_rules": triggered_rules,
        },
    }


def _coverage_assessment(total_sources: int, retained: int) -> CoverageAssessment:
    if retained == 0:
        return CoverageAssessment.limited
    if total_sources >= 10 and retained >= 5:
        return CoverageAssessment.broad
    if total_sources >= 3:
        return CoverageAssessment.moderate
    return CoverageAssessment.limited


def _build_overall_summary(
    risk: str,
    disposition: str,
    retained: int,
    flagged: int,
) -> str:
    if retained == 0:
        return (
            "No adverse evidence items were retained from open-web screening. "
            "Coverage is limited and manual review may still be warranted."
        )
    if risk == "high":
        return (
            f"Material adverse findings were identified across {flagged} flagged items "
            "with high-support evidence. Compliance review is required before proceeding."
        )
    if risk == "medium":
        return (
            f"Credible public-source concerns were identified in {retained} retained items. "
            "Compliance review is recommended before onboarding proceeds."
        )
    return (
        f"Screening retained {retained} evidence items with no material adverse findings "
        "above the low-support threshold."
    )


def _build_disposition_rationale(disposition: str) -> str:
    mapping = {
        "reject_or_hold": "High-risk findings with strong evidentiary support require hold or rejection.",
        "escalate_to_compliance": "At least one medium-to-high support adverse finding was identified in a material category.",
        "manual_review_recommended": "Medium-support findings warrant analyst review before a final decision.",
        "no_material_concern": "No material adverse findings above the low-support threshold were identified.",
    }
    return mapping.get(disposition, "Disposition determined by rule-based assessment.")


def _build_risk_flags(
    evidence: list[EvidenceItem],
    support_bands: dict[str, str],
) -> list[RiskFlag]:
    flags: list[RiskFlag] = []
    flag_idx = 1

    for item in evidence:
        band = support_bands.get(item.evidence_id, "low")
        if band not in ("medium", "high"):
            continue
        if not item.is_adverse:
            continue

        primary_category = item.risk_categories[0] if item.risk_categories else RiskCategory.other
        flags.append(
            RiskFlag(
                flag_id=f"RF-{flag_idx:03d}",
                category=primary_category,
                severity=item.rubric_assessment.adverse_severity,
                title=item.title[:120],
                description=item.rubric_assessment.justification,
                evidence_ids=[item.evidence_id],
            )
        )
        flag_idx += 1

    return flags


def _build_analyst_checklist(disposition: str) -> list[AnalystChecklistItem]:
    items: list[AnalystChecklistItem] = [
        AnalystChecklistItem(
            item_id="CHK-001",
            action="Verify entity identity against onboarding documents",
            priority=ChecklistPriority.high,
            reason="Confirm screened subject matches the evidence entity match assessment.",
        ),
        AnalystChecklistItem(
            item_id="CHK-002",
            action="Review retained evidence snippets and source URLs",
            priority=ChecklistPriority.medium,
            reason="Validate automated excerpts and confirm adverse context.",
        ),
    ]

    if disposition in ("escalate_to_compliance", "reject_or_hold"):
        items.append(
            AnalystChecklistItem(
                item_id="CHK-003",
                action="Escalate case to compliance officer for final disposition",
                priority=ChecklistPriority.high,
                reason="Automated screening identified elevated risk requiring compliance sign-off.",
            )
        )
    elif disposition == "manual_review_recommended":
        items.append(
            AnalystChecklistItem(
                item_id="CHK-003",
                action="Complete manual analyst review and document rationale",
                priority=ChecklistPriority.medium,
                reason="Medium-support findings require human judgment.",
            )
        )
    else:
        items.append(
            AnalystChecklistItem(
                item_id="CHK-003",
                action="Document screening outcome in case file",
                priority=ChecklistPriority.low,
                reason="No material concern identified; record screening completion.",
            )
        )

    return items


def _build_rubric_definition(rules_config: dict) -> RubricDefinition:
    return RubricDefinition(
        rubric_version=rules_config.get("rubric_version", "v1"),
        component_scales=ComponentScales(
            entity_match=[EntityMatch.low, EntityMatch.medium, EntityMatch.high],
            source_tier=[SourceTier.tier_1, SourceTier.tier_2, SourceTier.tier_3],
            adverse_severity=[
                AdverseSeverity.low,
                AdverseSeverity.medium,
                AdverseSeverity.high,
                AdverseSeverity.critical,
            ],
            recency=[Recency.stale, Recency.recent, Recency.current],
            jurisdiction_relevance=[
                EntityMatch.low,
                EntityMatch.medium,
                EntityMatch.high,
            ],
            corroboration=[
                Corroboration.none,
                Corroboration.single_source,
                Corroboration.multi_source,
            ],
            case_linkage=[EntityMatch.low, EntityMatch.medium, EntityMatch.high],
        ),
        support_band_rules=rules_config.get("support_band_rules", []),
        case_risk_rules=rules_config.get("case_risk_rules", []),
    )


def assemble_report(checkpoint4: dict) -> ReputationScreeningReport:
    settings = get_settings()
    rules_config = load_rules_config()

    run_id = checkpoint4["run_id"]
    subject = Subject.model_validate(checkpoint4["subject"])
    screening_scope = ScreeningScope.model_validate(checkpoint4["screening_scope"])
    processed_items = checkpoint4.get("processed_items", [])
    classifications_raw = checkpoint4.get("classifications", [])

    classifications = [EvidenceClassification.model_validate(c) for c in classifications_raw]
    class_by_id = {c.evidence_id: c for c in classifications}

    rubric_items: list[RubricItem] = []
    support_bands: dict[str, str] = {}
    support_rules: dict[str, str] = {}

    evidence: list[EvidenceItem] = []

    for proc in processed_items:
        eid = proc["evidence_id"]
        cls = class_by_id.get(eid)
        if not cls:
            continue

        rubric_item = RubricItem(
            evidence_id=eid,
            entity_match=cls.entity_match.value,
            source_tier=cls.source_tier.value,
            adverse_severity=cls.adverse_severity.value,
            recency=cls.recency.value,
            jurisdiction_relevance=cls.jurisdiction_relevance.value,
            corroboration=cls.corroboration.value,
            case_linkage=cls.case_linkage.value,
            risk_categories=[rc.value for rc in cls.risk_categories],
        )
        rubric_items.append(rubric_item)

        band, rule_id = compute_support_band(rubric_item)
        support_bands[eid] = band
        support_rules[eid] = rule_id

        if cls.risk_categories:
            risk_cats = cls.risk_categories
        else:
            risk_cats = [
                RiskCategory(rc) for rc in proc.get("risk_categories", ["other"])
            ]
        if not risk_cats:
            risk_cats = [RiskCategory.other]

        evidence.append(
            EvidenceItem(
                evidence_id=eid,
                source_type=EvidenceSourceType(proc.get("source_type", "other")),
                source_name=proc.get("source_name", "unknown"),
                title=proc.get("title", "Untitled"),
                url=proc.get("url", "https://example.com"),
                publication_date=proc.get("publication_date"),
                snippet=proc.get("snippet", ""),
                language=proc.get("language"),
                risk_categories=risk_cats,
                rubric_assessment=RubricAssessment(
                    entity_match=cls.entity_match,
                    source_tier=cls.source_tier,
                    adverse_severity=cls.adverse_severity,
                    recency=cls.recency,
                    jurisdiction_relevance=cls.jurisdiction_relevance,
                    corroboration=cls.corroboration,
                    case_linkage=cls.case_linkage,
                    justification=cls.justification,
                ),
                support_band=SupportBand(band),
                support_rule_triggered=rule_id,
                is_adverse=proc.get("is_adverse", False),
            )
        )

    case_result = compute_case_risk(processed_items, rubric_items, support_bands, rules_config)
    total_sources = checkpoint4.get("total_sources_reviewed", 0)
    items_discarded = checkpoint4.get("items_discarded", 0)
    flagged = sum(1 for e in evidence if e.is_adverse)

    coverage = _coverage_assessment(total_sources, len(evidence))
    overall_summary = _build_overall_summary(
        case_result["overall_risk_level"],
        case_result["recommended_disposition"],
        len(evidence),
        flagged,
    )

    assessment = Assessment(
        overall_risk_level=OverallRiskLevel(case_result["overall_risk_level"]),
        overall_summary=overall_summary,
        coverage_assessment=coverage,
        coverage_notes=(
            "Open-web coverage is sufficient for initial review but specialist "
            "subscription databases were not searched."
            if coverage != CoverageAssessment.limited
            else "Limited open-web coverage; no or few adverse items retained."
        ),
        recommended_disposition=RecommendedDisposition(case_result["recommended_disposition"]),
        disposition_rationale=_build_disposition_rationale(case_result["recommended_disposition"]),
        determination_basis=DeterminationBasis(
            method=DeterminationMethod.rule_based_v1,
            support_summary=SupportSummary(**case_result["determination_basis"]["support_summary"]),
            triggered_rules=case_result["determination_basis"]["triggered_rules"],
        ),
    )

    risk_flags = _build_risk_flags(evidence, support_bands)
    analyst_checklist = _build_analyst_checklist(case_result["recommended_disposition"])

    processing_notes = [
        f"Pipeline run {run_id} completed via rule_based_v1.",
        f"Items discarded during sandbox processing: {items_discarded}.",
    ]

    entity_resolution_path = (
        get_settings().runs_path / run_id / "checkpoint_entity_resolution.json"
    )
    if entity_resolution_path.exists():
        with open(entity_resolution_path, encoding="utf-8") as f:
            er_checkpoint = json.load(f)
        entity_resolution = er_checkpoint.get("entity_resolution", {})
        clarified = er_checkpoint.get("clarification_received", False)
        level = entity_resolution.get("ambiguity_level", "unknown")
        codes = entity_resolution.get("reason_codes", [])
        processing_notes.append(
            f"Entity resolution: ambiguity_level={level}, reason_codes={codes}, "
            f"clarified={'yes' if clarified else 'no'}."
        )
        if level == "medium":
            screening_scope.screening_limitations.append(
                "Entity resolution confidence is moderate; results may include weaker entity matches."
            )

    audit_trail = AuditTrail(
        total_sources_reviewed=total_sources,
        total_evidence_items_retained=len(evidence),
        false_positive_notes=[],
        processing_notes=processing_notes,
    )

    report = ReputationScreeningReport(
        report_metadata=ReportMetadata(
            report_id=f"RSR-{run_id}",
            generated_at=datetime.now(timezone.utc).isoformat(),
            agent_version=settings.agent_version,
            workflow_run_id=run_id,
            data_sources=[DataSource.bright_data, DataSource.search_engine],
        ),
        subject=subject,
        screening_scope=screening_scope,
        rubric_definition=_build_rubric_definition(rules_config),
        assessment=assessment,
        risk_flags=risk_flags,
        evidence=evidence,
        analyst_checklist=analyst_checklist,
        audit_trail=audit_trail,
    )

    return report


def run_stage5(checkpoint4: dict) -> dict:
    report = assemble_report(checkpoint4)
    return {
        "run_id": checkpoint4["run_id"],
        "stage": "rule_engine",
        "status": "complete",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "report": report.model_dump(mode="json"),
    }
