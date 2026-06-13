"""Stage 4: LLM rubric classification (TokenRouter, OpenRouter, or Kimi)."""

from datetime import datetime, timezone

from pydantic import ValidationError

from schemas.report import EvidenceClassification
from schemas.rubric import (
    AdverseSeverity,
    Corroboration,
    EntityMatch,
    Recency,
    RiskCategory,
    SourceTier,
)
from stages.llm_client import active_llm_model, complete_json, llm_configured, parse_json_object
from logging_config import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """
You are a compliance screening analyst assistant.
Your task is to classify each evidence item using the provided rubric.
You must output ONLY a valid JSON object with an "items" array. No preamble, no explanation, no markdown.
Classify each item strictly against the rubric definitions provided.
Never invent findings not present in the provided text.
If a component cannot be determined from the text, default to the lowest band.
"""

RUBRIC_DEFINITIONS = """
entity_match:
  high = exact name plus at least one supporting attribute (company, role, country)
  medium = probable name match but one supporting attribute missing or ambiguous
  low = partial or ambiguous name match only

source_tier:
  tier_1 = official regulator, court record, major mainstream press (Reuters, FT, Bloomberg, ST)
  tier_2 = established trade or regional press with documented editorial standards
  tier_3 = blog, forum, opinion site, low-attribution content

adverse_severity:
  critical = formal enforcement, sanctions designation, criminal conviction
  high = active investigation, fraud allegation, regulatory action, litigation filed
  medium = material complaints, repeated negative reporting, non-trivial controversy
  low = mild reputational concern, opinion, editorial criticism

recency:
  current = published within 12 months
  recent = published 1-3 years ago
  stale = published more than 3 years ago

jurisdiction_relevance:
  high = source and event directly relevant to the screened jurisdictions
  medium = indirect regional relevance
  low = unrelated or distant jurisdiction

corroboration:
  multi_source = the same event or allegation is reported by multiple independent sources
  single_source = appears in one source only
  none = no adverse finding to corroborate

case_linkage:
  high = directly relevant to the type of risk being screened (financial crime, reputational)
  medium = tangentially relevant
  low = weak or unclear link to the case
"""


def _conservative_classification(evidence_id: str) -> EvidenceClassification:
    return EvidenceClassification(
        evidence_id=evidence_id,
        entity_match=EntityMatch.low,
        source_tier=SourceTier.tier_3,
        adverse_severity=AdverseSeverity.low,
        recency=Recency.stale,
        jurisdiction_relevance=EntityMatch.low,
        corroboration=Corroboration.none,
        case_linkage=EntityMatch.low,
        justification="Classification defaulted to lowest bands due to validation or API failure.",
        risk_categories=[RiskCategory.other],
    )


def _build_user_prompt(processed_items: list[dict], subject: dict, error_hint: str | None = None) -> str:
    import json

    items_json = json.dumps(processed_items, indent=2)
    subject_json = json.dumps(subject, indent=2)
    error_block = f"\nPrevious validation error to fix: {error_hint}\n" if error_hint else ""

    return f"""
Subject: {subject_json}

Rubric definitions:
{RUBRIC_DEFINITIONS}

Evidence items to classify:
{items_json}
{error_block}
Return a JSON object with an "items" array. Each element must contain:
- evidence_id (from input)
- entity_match (low|medium|high)
- source_tier (tier_1|tier_2|tier_3)
- adverse_severity (low|medium|high|critical)
- recency (stale|recent|current)
- jurisdiction_relevance (low|medium|high)
- corroboration (none|single_source|multi_source)
- case_linkage (low|medium|high)
- justification (1-2 sentences grounded in the excerpt)
- risk_categories (array of category strings from the rubric)

Output only the JSON object.
"""


def _parse_llm_response(raw: str) -> list[dict]:
    parsed = parse_json_object(raw)
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        for key in ("items", "evidence", "classifications", "results"):
            if key in parsed and isinstance(parsed[key], list):
                return parsed[key]
    raise ValueError("LLM response did not contain a recognizable items array")


def _validate_classifications(raw_items: list[dict]) -> tuple[list[EvidenceClassification], str | None]:
    validated: list[EvidenceClassification] = []
    errors: list[str] = []

    for item in raw_items:
        try:
            validated.append(EvidenceClassification.model_validate(item))
        except ValidationError as e:
            errors.append(f"{item.get('evidence_id', '?')}: {e}")

    if errors:
        return validated, "; ".join(errors)
    return validated, None


def classify_evidence_items(
    processed_items: list[dict],
    subject: dict,
) -> list[EvidenceClassification]:
    if not processed_items:
        return []

    if not llm_configured():
        logger.warning("LLM not configured; using conservative classifications for %d items", len(processed_items))
        return [
            _conservative_classification(item["evidence_id"])
            for item in processed_items
        ]

    error_hint: str | None = None
    validated: list[EvidenceClassification] = []

    for attempt in range(2):
        try:
            raw = complete_json(
                SYSTEM_PROMPT,
                _build_user_prompt(processed_items, subject, error_hint),
            )
        except Exception as e:
            logger.exception("LLM classification attempt %d failed: %s", attempt + 1, e)
            raise
        parsed_items = _parse_llm_response(raw)
        validated, error_hint = _validate_classifications(parsed_items)

        if error_hint is None and len(validated) == len(processed_items):
            logger.info("LLM classified %d evidence items", len(validated))
            return validated

        logger.warning("LLM classification validation attempt %d: %s", attempt + 1, error_hint)

        if attempt == 1:
            break

    logger.warning(
        "LLM classification incomplete; filling %d items with conservative defaults",
        len(processed_items) - len(validated),
    )
    by_id = {c.evidence_id: c for c in validated}
    result: list[EvidenceClassification] = []
    for item in processed_items:
        eid = item["evidence_id"]
        result.append(by_id.get(eid, _conservative_classification(eid)))
    return result


def run_stage4(checkpoint3: dict) -> dict:
    from config import get_settings

    processed_items = checkpoint3.get("processed_items", [])
    subject = checkpoint3.get("subject", {})
    settings = get_settings()

    classifications = classify_evidence_items(processed_items, subject)

    return {
        "run_id": checkpoint3["run_id"],
        "stage": "llm_reasoning",
        "status": "complete",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "subject": subject,
        "screening_scope": checkpoint3.get("screening_scope"),
        "processed_items": processed_items,
        "classifications": [c.model_dump() for c in classifications],
        "total_sources_reviewed": checkpoint3.get("total_sources_reviewed", 0),
        "items_discarded": checkpoint3.get("items_discarded", 0),
        "llm_provider": settings.llm_provider,
        "llm_model": active_llm_model(),
    }
