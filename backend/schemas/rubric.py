from enum import Enum


class EntityMatch(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class SourceTier(str, Enum):
    tier_1 = "tier_1"
    tier_2 = "tier_2"
    tier_3 = "tier_3"


class AdverseSeverity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class Recency(str, Enum):
    stale = "stale"
    recent = "recent"
    current = "current"


class Corroboration(str, Enum):
    none = "none"
    single_source = "single_source"
    multi_source = "multi_source"


class SupportBand(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class OverallRiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class RecommendedDisposition(str, Enum):
    no_material_concern = "no_material_concern"
    manual_review_recommended = "manual_review_recommended"
    escalate_to_compliance = "escalate_to_compliance"
    reject_or_hold = "reject_or_hold"


class CoverageAssessment(str, Enum):
    limited = "limited"
    moderate = "moderate"
    broad = "broad"


class DeterminationMethod(str, Enum):
    rule_based_v1 = "rule_based_v1"


class SubjectType(str, Enum):
    individual = "individual"
    organization = "organization"


class DataSource(str, Enum):
    bright_data = "bright_data"
    search_engine = "search_engine"
    news_site = "news_site"
    company_website = "company_website"
    registry_site = "registry_site"
    manual_input = "manual_input"


class RiskCategory(str, Enum):
    fraud = "fraud"
    financial_crime = "financial_crime"
    sanctions = "sanctions"
    regulatory = "regulatory"
    litigation = "litigation"
    corruption = "corruption"
    political_exposure = "political_exposure"
    reputational = "reputational"
    adverse_media = "adverse_media"
    ownership_opacity = "ownership_opacity"
    identity_mismatch = "identity_mismatch"
    other = "other"


class EvidenceSourceType(str, Enum):
    news = "news"
    blog = "blog"
    company_website = "company_website"
    registry = "registry"
    court_record = "court_record"
    watchlist_reference = "watchlist_reference"
    other = "other"


class RiskFlagStatus(str, Enum):
    open = "open"
    mitigated = "mitigated"
    dismissed = "dismissed"
    needs_review = "needs_review"


class ChecklistPriority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class ChecklistStatus(str, Enum):
    pending = "pending"
    completed = "completed"
    not_applicable = "not_applicable"
