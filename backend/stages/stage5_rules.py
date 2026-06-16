"""Stage 5: Deterministic rule engine and final report assembly."""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI

from config import get_settings
from logging_config import get_logger

logger = get_logger(__name__)
from schemas.report import (
    AnalystChecklistItem,
    Assessment,
    AuditTrail,
    ComponentScales,
    DashboardSummary,
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


def _build_memo(
    subject: Subject,
    overall_summary: str,
    disposition: str,
    disposition_rationale: str,
    support_summary: dict,
    triggered_rules: list[str],
    risk_flags: list[RiskFlag],
) -> str:
    """Deterministic compliance memo assembled from rule-engine outputs."""
    lines = [
        f"Subject: {subject.primary_name}",
        f"Type: {subject.subject_type.value}",
    ]
    if subject.country:
        lines.append(f"Country: {subject.country}")
    if subject.industry:
        lines.append(f"Industry: {subject.industry}")
    lines.extend(["", "Executive Summary", overall_summary, ""])
    lines.append(f"Recommended Disposition: {disposition.replace('_', ' ').title()}")
    lines.append(disposition_rationale)
    lines.extend(
        [
            "",
            "Support Summary",
            (
                f"High-support evidence: {support_summary.get('high_support_evidence_count', 0)}; "
                f"Medium-support: {support_summary.get('medium_support_evidence_count', 0)}; "
                f"Low-support: {support_summary.get('low_support_evidence_count', 0)}; "
                f"Material categories: {support_summary.get('material_category_count', 0)}; "
                f"Tier-1 hits: {support_summary.get('official_or_tier_1_hits', 0)}."
            ),
        ]
    )
    if triggered_rules:
        lines.extend(["", "Triggered Rules"])
        for rule in triggered_rules[:8]:
            lines.append(f"- {rule}")
    if risk_flags:
        lines.extend(["", "Key Risk Flags"])
        for flag in risk_flags[:5]:
            lines.append(f"- [{flag.severity.value}] {flag.title}: {flag.description[:240]}")
    lines.extend(
        [
            "",
            "This memo was generated deterministically from open-web screening results. "
            "Human compliance review is required before any onboarding decision.",
        ]
    )
    return "\n".join(lines)


def _build_sensenova_memo_prompt(
    subject: Subject,
    overall_summary: str,
    disposition: str,
    disposition_rationale: str,
    support_summary: dict,
    triggered_rules: list[str],
    risk_flags: list[RiskFlag],
    deterministic_memo: str,
) -> tuple[str, str]:
    system_prompt = (
        "You write compliance memos for a reputational screening workflow. "
        "Preserve the facts and disposition in the provided draft. "
        "Return plain text only, without markdown fences or bullet rewrites that add new facts."
    )
    triggered_rule_lines = [f"- {rule}" for rule in triggered_rules[:8]] or ["- None"]
    risk_flag_lines = [
        f"- [{flag.severity.value}] {flag.title}: {flag.description[:240]}"
        for flag in risk_flags[:5]
    ] or ["- None"]
    user_prompt = "\n".join(
        [
            f"Subject: {subject.primary_name}",
            f"Type: {subject.subject_type.value}",
            f"Country: {subject.country or 'N/A'}",
            f"Industry: {subject.industry or 'N/A'}",
            "",
            f"Overall summary: {overall_summary}",
            f"Recommended disposition: {disposition.replace('_', ' ').title()}",
            f"Disposition rationale: {disposition_rationale}",
            "",
            "Support summary:",
            (
                f"High-support evidence: {support_summary.get('high_support_evidence_count', 0)}; "
                f"Medium-support: {support_summary.get('medium_support_evidence_count', 0)}; "
                f"Low-support: {support_summary.get('low_support_evidence_count', 0)}; "
                f"Material categories: {support_summary.get('material_category_count', 0)}; "
                f"Tier-1 hits: {support_summary.get('official_or_tier_1_hits', 0)}."
            ),
            "",
            "Triggered rules:",
            *triggered_rule_lines,
            "",
            "Key risk flags:",
            *risk_flag_lines,
            "",
            "Draft memo to polish:",
            deterministic_memo,
        ]
    )
    return system_prompt, user_prompt


def _maybe_generate_sensenova_memo(
    subject: Subject,
    overall_summary: str,
    disposition: str,
    disposition_rationale: str,
    support_summary: dict,
    triggered_rules: list[str],
    risk_flags: list[RiskFlag],
    deterministic_memo: str,
    strict: bool = False,
) -> str:
    settings = get_settings()
    if not settings.sensenova_configured:
        if strict:
            raise RuntimeError(
                "SenseNova is not configured. Set SENSENOVA_API_KEY, SENSENOVA_BASE_URL, and SENSENOVA_MODEL."
            )
        return deterministic_memo

    system_prompt, user_prompt = _build_sensenova_memo_prompt(
        subject,
        overall_summary,
        disposition,
        disposition_rationale,
        support_summary,
        triggered_rules,
        risk_flags,
        deterministic_memo,
    )

    client = OpenAI(
        base_url=settings.sensenova_base_url,
        api_key=settings.sensenova_api_key,
    )

    try:
        response = client.chat.completions.create(
            model=settings.sensenova_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=settings.llm_max_output_tokens,
        )
        content = (response.choices[0].message.content or "").strip()
        if not content:
            raise RuntimeError("SenseNova returned an empty memo")
        logger.info("SenseNova memo generation succeeded model=%s", settings.sensenova_model)
        return content
    except Exception:
        if strict:
            raise
        logger.exception(
            "SenseNova memo generation failed model=%s; using deterministic memo",
            settings.sensenova_model,
        )
        return deterministic_memo


def generate_sensenova_memo_from_report(report_dict: dict) -> str:
    """Generate a memo from an existing final report using SenseNova only (no fallback)."""
    report = ReputationScreeningReport.model_validate(report_dict)
    assessment = report.assessment
    determination = assessment.determination_basis
    support_summary = determination.support_summary.model_dump(mode="json")
    triggered_rules = determination.triggered_rules

    deterministic_memo = assessment.memo or _build_memo(
        report.subject,
        assessment.overall_summary,
        assessment.recommended_disposition.value,
        assessment.disposition_rationale,
        support_summary,
        triggered_rules,
        report.risk_flags,
    )

    return _maybe_generate_sensenova_memo(
        report.subject,
        assessment.overall_summary,
        assessment.recommended_disposition.value,
        assessment.disposition_rationale,
        support_summary,
        triggered_rules,
        report.risk_flags,
        deterministic_memo,
        strict=True,
    )


def _generate_kimi_memo(
    subject: Subject,
    overall_summary: str,
    disposition: str,
    disposition_rationale: str,
    support_summary: dict,
    triggered_rules: list[str],
    risk_flags: list[RiskFlag],
    deterministic_memo: str,
) -> str:
    settings = get_settings()
    if not settings.kimi_api_key or not settings.kimi_base_url or not settings.kimi_model:
        raise RuntimeError(
            "Kimi is not configured. Set KIMI_API_KEY, KIMI_BASE_URL, and KIMI_MODEL."
        )

    system_prompt, user_prompt = _build_sensenova_memo_prompt(
        subject,
        overall_summary,
        disposition,
        disposition_rationale,
        support_summary,
        triggered_rules,
        risk_flags,
        deterministic_memo,
    )

    client = OpenAI(
        base_url=settings.kimi_base_url,
        api_key=settings.kimi_api_key,
    )

    response = client.chat.completions.create(
        model=settings.kimi_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=settings.llm_max_output_tokens,
    )
    content = (response.choices[0].message.content or "").strip()
    if not content:
        raise RuntimeError("Kimi returned an empty memo")
    logger.info("Kimi memo generation succeeded model=%s", settings.kimi_model)
    return content


def generate_kimi_memo_from_report(report_dict: dict) -> str:
    """Generate a memo from an existing final report using Kimi only."""
    report = ReputationScreeningReport.model_validate(report_dict)
    assessment = report.assessment
    determination = assessment.determination_basis
    support_summary = determination.support_summary.model_dump(mode="json")
    triggered_rules = determination.triggered_rules

    deterministic_memo = assessment.memo or _build_memo(
        report.subject,
        assessment.overall_summary,
        assessment.recommended_disposition.value,
        assessment.disposition_rationale,
        support_summary,
        triggered_rules,
        report.risk_flags,
    )

    return _generate_kimi_memo(
        report.subject,
        assessment.overall_summary,
        assessment.recommended_disposition.value,
        assessment.disposition_rationale,
        support_summary,
        triggered_rules,
        report.risk_flags,
        deterministic_memo,
    )


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
    non_adverse_retained = sum(1 for e in evidence if not e.is_adverse)

    coverage = _coverage_assessment(total_sources, len(evidence))
    coverage_notes = (
        "Open-web coverage is sufficient for initial review but specialist "
        "subscription databases were not searched."
        if coverage != CoverageAssessment.limited
        else "Limited open-web coverage; no or few adverse items retained."
    )
    if non_adverse_retained:
        coverage_notes += (
            f" {non_adverse_retained} retained item(s) were not flagged as adverse "
            "and do not appear in risk_flags."
        )
    overall_summary = _build_overall_summary(
        case_result["overall_risk_level"],
        case_result["recommended_disposition"],
        len(evidence),
        flagged,
    )

    risk_flags = _build_risk_flags(evidence, support_bands)
    analyst_checklist = _build_analyst_checklist(case_result["recommended_disposition"])

    support_summary_dict = case_result["determination_basis"]["support_summary"]
    triggered_rules_list = case_result["determination_basis"]["triggered_rules"]
    disposition_rationale = _build_disposition_rationale(case_result["recommended_disposition"])
    memo_text = _build_memo(
        subject,
        overall_summary,
        case_result["recommended_disposition"],
        disposition_rationale,
        support_summary_dict,
        triggered_rules_list,
        risk_flags,
    )
    memo_text = _maybe_generate_sensenova_memo(
        subject,
        overall_summary,
        case_result["recommended_disposition"],
        disposition_rationale,
        support_summary_dict,
        triggered_rules_list,
        risk_flags,
        memo_text,
    )

    assessment = Assessment(
        overall_risk_level=OverallRiskLevel(case_result["overall_risk_level"]),
        overall_summary=overall_summary,
        coverage_assessment=coverage,
        coverage_notes=coverage_notes,
        recommended_disposition=RecommendedDisposition(case_result["recommended_disposition"]),
        disposition_rationale=disposition_rationale,
        determination_basis=DeterminationBasis(
            method=DeterminationMethod.rule_based_v1,
            support_summary=SupportSummary(**support_summary_dict),
            triggered_rules=triggered_rules_list,
        ),
        memo=memo_text,
    )

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

    dashboard_summary = DashboardSummary(
        risk_category=_risk_category_label(case_result["overall_risk_level"]),
        support_summary_line=(
            f"{support_summary_dict.get('high_support_evidence_count', 0)} high / "
            f"{support_summary_dict.get('medium_support_evidence_count', 0)} med / "
            f"{support_summary_dict.get('low_support_evidence_count', 0)} low"
        ),
        top_triggered_rule=(triggered_rules_list[0] if triggered_rules_list else "No rules triggered"),
        confidence_label=coverage.value.title(),
        recommendation_label=case_result["recommended_disposition"].replace("_", " ").title(),
        entity_match_score=_entity_match_score(evidence),
        entity_match_level=_entity_match_level(evidence),
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
        dashboard_summary=dashboard_summary,
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


def _entity_match_score(evidence: list[EvidenceItem]) -> int:
    score_map = {"high": 90, "medium": 65, "low": 35}
    best_score = 0
    for item in evidence:
        score = score_map.get(item.rubric_assessment.entity_match.value, 35)
        if score > best_score:
            best_score = score
    return best_score


def _entity_match_level(evidence: list[EvidenceItem]) -> str:
    score = _entity_match_score(evidence)
    if score >= 90:
        return "High"
    if score >= 65:
        return "Medium"
    return "Low"


def _risk_category_label(level: str) -> str:
    return {
        "low": "Low Risk",
        "medium": "Medium Risk",
        "high": "High Risk",
        "critical": "Critical Risk",
    }.get(level, "Medium Risk")
