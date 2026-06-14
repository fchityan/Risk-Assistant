from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from schemas.rubric import (
    AdverseSeverity,
    ChecklistPriority,
    ChecklistStatus,
    Corroboration,
    CoverageAssessment,
    DataSource,
    DeterminationMethod,
    EntityMatch,
    EvidenceSourceType,
    OverallRiskLevel,
    Recency,
    RecommendedDisposition,
    RiskCategory,
    RiskFlagStatus,
    SourceTier,
    SubjectType,
    SupportBand,
)


class ReportMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_id: str
    generated_at: str
    agent_version: str
    workflow_run_id: str
    data_sources: list[DataSource] = Field(min_length=1)


class Subject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_type: SubjectType
    primary_name: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    country: Optional[str] = None
    industry: Optional[str] = None
    known_associations: list[str] = Field(default_factory=list)
    input_notes: Optional[str] = None


class ScreeningScope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    jurisdictions: list[str]
    languages: list[str]
    lookback_period_years: int = Field(ge=1, le=20)
    search_queries: list[str] = Field(min_length=1)
    screening_limitations: list[str] = Field(default_factory=list)


class ComponentScales(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_match: list[EntityMatch]
    source_tier: list[SourceTier]
    adverse_severity: list[AdverseSeverity]
    recency: list[Recency]
    jurisdiction_relevance: list[EntityMatch]
    corroboration: list[Corroboration]
    case_linkage: list[EntityMatch]


class RubricDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rubric_version: str
    component_scales: ComponentScales
    support_band_rules: list[str]
    case_risk_rules: list[str]


class SupportSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    high_support_evidence_count: int = Field(ge=0)
    medium_support_evidence_count: int = Field(ge=0)
    low_support_evidence_count: int = Field(ge=0)
    material_category_count: int = Field(ge=0)
    official_or_tier_1_hits: int = Field(ge=0)


class DeterminationBasis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: DeterminationMethod
    support_summary: SupportSummary
    triggered_rules: list[str]


class Assessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall_risk_level: OverallRiskLevel
    overall_summary: str = Field(min_length=20)
    coverage_assessment: CoverageAssessment
    coverage_notes: Optional[str] = None
    recommended_disposition: RecommendedDisposition
    disposition_rationale: str = ""
    determination_basis: DeterminationBasis
    memo: Optional[str] = None


class RiskFlag(BaseModel):
    model_config = ConfigDict(extra="forbid")

    flag_id: str
    category: RiskCategory
    severity: AdverseSeverity
    title: str
    description: str
    status: RiskFlagStatus = RiskFlagStatus.open
    evidence_ids: list[str] = Field(min_length=1)
    analyst_note: Optional[str] = None


class RubricAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_match: EntityMatch
    source_tier: SourceTier
    adverse_severity: AdverseSeverity
    recency: Recency
    jurisdiction_relevance: EntityMatch
    corroboration: Corroboration
    case_linkage: EntityMatch
    justification: str


class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    source_type: EvidenceSourceType
    source_name: str
    title: str
    url: str
    publication_date: Optional[str] = None
    snippet: str
    language: Optional[str] = None
    risk_categories: list[RiskCategory]
    rubric_assessment: RubricAssessment
    support_band: SupportBand
    support_rule_triggered: Optional[str] = None
    is_adverse: bool = False


class AnalystChecklistItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str
    action: str
    priority: ChecklistPriority
    reason: str
    status: ChecklistStatus = ChecklistStatus.pending


class AuditTrail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_sources_reviewed: int = Field(ge=0)
    total_evidence_items_retained: int = Field(ge=0)
    false_positive_notes: list[str]
    processing_notes: list[str]


class DashboardSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    risk_category: str
    support_summary_line: str
    top_triggered_rule: str
    confidence_label: str
    recommendation_label: str
    entity_match_score: int = Field(ge=0, le=100)
    entity_match_level: str


class ReputationScreeningReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_metadata: ReportMetadata
    subject: Subject
    screening_scope: ScreeningScope
    rubric_definition: RubricDefinition
    assessment: Assessment
    risk_flags: list[RiskFlag]
    evidence: list[EvidenceItem]
    analyst_checklist: list[AnalystChecklistItem]
    audit_trail: AuditTrail
    dashboard_summary: Optional[DashboardSummary] = None


# Stage 4 LLM output (classification only, before support_band assignment)
class EvidenceClassification(BaseModel):
    evidence_id: str
    entity_match: EntityMatch
    source_tier: SourceTier
    adverse_severity: AdverseSeverity
    recency: Recency
    jurisdiction_relevance: EntityMatch
    corroboration: Corroboration
    case_linkage: EntityMatch
    justification: str
    risk_categories: list[RiskCategory] = Field(default_factory=list)


class ScreenRequest(BaseModel):
    subject_type: SubjectType
    primary_name: str = Field(min_length=1)
    country: Optional[str] = None
    industry: Optional[str] = None
    known_associations: list[str] = Field(default_factory=list)
    input_notes: Optional[str] = None
    aliases: list[str] = Field(default_factory=list)
