"""Stage 1.5: Entity resolution and clarification gate."""

import json
from datetime import datetime, timezone

from async_utils import run_coroutine_sync
from config import get_settings
from logging_config import get_logger
from schemas.resolution import (
    CandidateEntity,
    ClarificationForm,
    ClarificationQuestion,
    ClarificationRequest,
    EntityResolution,
    ResolvedSubject,
    SubjectFieldBundle,
)
from schemas.report import Subject
from stages.llm_client import complete_json, llm_configured, parse_json_object
from stages.stage1_subject import build_screening_scope, subject_from_dict
from stages.stage2_collect import discover_candidates

logger = get_logger(__name__)

DISCOVERY_SYSTEM_PROMPT = """
You are an entity resolution assistant for adverse media screening.
Given a subject name and search snippets, extract candidate entities and inferred attributes.
Output ONLY valid JSON with:
- candidate_entities: array of {candidate_id, name, country, industry, why_shown}
- inferred: {country, industry, known_associations}
- model_ambiguity_hint: low|medium|high (advisory only)
Never invent facts not supported by snippets. Use null for unknown fields.
"""


def _bundle_from_subject(subject: Subject) -> SubjectFieldBundle:
    return SubjectFieldBundle(
        country=subject.country,
        industry=subject.industry,
        known_associations=list(subject.known_associations),
    )


def _empty_bundle() -> SubjectFieldBundle:
    return SubjectFieldBundle()


def _user_has_identifier(subject: Subject) -> bool:
    return bool(subject.country) or bool(subject.known_associations)


def _merge_effective_subject(
    subject: Subject,
    resolved: ResolvedSubject,
    selected_candidate: CandidateEntity | None = None,
) -> Subject:
    country = (
        resolved.confirmed.country
        or resolved.inferred.country
        or resolved.user_provided.country
        or subject.country
    )
    industry = (
        resolved.confirmed.industry
        or resolved.inferred.industry
        or resolved.user_provided.industry
        or subject.industry
    )
    associations = list(
        resolved.confirmed.known_associations
        or resolved.inferred.known_associations
        or resolved.user_provided.known_associations
        or subject.known_associations
    )
    if selected_candidate and selected_candidate.name:
        primary_name = selected_candidate.name
    else:
        primary_name = subject.primary_name

    return Subject(
        subject_type=subject.subject_type,
        primary_name=primary_name,
        aliases=list(subject.aliases),
        country=country,
        industry=industry,
        known_associations=associations,
        input_notes=subject.input_notes,
    )


def _compute_ambiguity(
    candidates: list[CandidateEntity],
    user_has_id: bool,
    clarified: bool,
    inferred: SubjectFieldBundle,
    model_hint: str,
) -> EntityResolution:
    reason_codes: list[str] = []

    if user_has_id:
        return EntityResolution(
            ambiguity_level="low",
            reason_codes=["USER_PROVIDED_IDENTIFIER"],
            action="continue",
        )

    if clarified:
        return EntityResolution(
            ambiguity_level="low",
            reason_codes=["CLARIFIED"],
            action="continue",
        )

    if not candidates:
        reason_codes.append("NO_ENRICHMENT_FOUND")
        return EntityResolution(
            ambiguity_level="medium",
            reason_codes=reason_codes,
            action="continue_limited",
        )

    distinct_countries = {c.country for c in candidates if c.country}
    plausible = [c for c in candidates if c.name]

    if len(plausible) >= 2 and len(distinct_countries) >= 2:
        reason_codes.extend(["MULTIPLE_PLAUSIBLE_ORGS", "NO_CONFIRMED_COUNTRY"])
        if model_hint == "high":
            reason_codes.append("MIXED_NEWS_MATCHES")
        return EntityResolution(
            ambiguity_level="high",
            reason_codes=reason_codes,
            action="clarification_required",
        )

    if len(plausible) == 1:
        reason_codes.append("SINGLE_DOMINANT_CANDIDATE")
        level = "low" if inferred.country else "medium"
        if not inferred.country:
            reason_codes.append("NO_CONFIRMED_COUNTRY")
        return EntityResolution(
            ambiguity_level=level,
            reason_codes=reason_codes,
            action="continue" if level == "low" else "continue_limited",
        )

    if len(plausible) >= 2:
        reason_codes.extend(["MULTIPLE_PLAUSIBLE_ORGS", "NO_CONFIRMED_COUNTRY"])
        return EntityResolution(
            ambiguity_level="high",
            reason_codes=reason_codes,
            action="clarification_required",
        )

    reason_codes.append("NO_ENRICHMENT_FOUND")
    return EntityResolution(
        ambiguity_level="medium",
        reason_codes=reason_codes,
        action="continue_limited",
    )


def _build_clarification_form(
    candidates: list[CandidateEntity],
    inferred: SubjectFieldBundle,
) -> ClarificationForm:
    country_options = sorted(
        {c.country for c in candidates if c.country}
        | ({inferred.country} if inferred.country else set())
        | {"Other", "Unknown"}
    )
    industry_options = sorted(
        {c.industry for c in candidates if c.industry}
        | ({inferred.industry} if inferred.industry else set())
        | {"Other", "Unknown"}
    )

    questions = [
        ClarificationQuestion(
            field="country",
            label="Which country is the subject primarily associated with?",
            type="select",
            options=country_options,
            required=True,
        ),
        ClarificationQuestion(
            field="industry",
            label="Which industry best matches the subject?",
            type="select",
            options=industry_options,
            required=False,
        ),
        ClarificationQuestion(
            field="known_associations",
            label="Any related entity, website, or parent company?",
            type="text",
            required=False,
        ),
    ]
    return ClarificationForm(questions=questions, candidate_entities=candidates)


async def _run_llm_discovery(
    subject: Subject,
    serp_items: list[dict],
) -> tuple[list[CandidateEntity], SubjectFieldBundle, str]:
    if not llm_configured() or not serp_items:
        return [], _empty_bundle(), "medium"

    user_prompt = json.dumps(
        {
            "subject_type": subject.subject_type.value,
            "primary_name": subject.primary_name,
            "serp_items": serp_items,
        },
        indent=2,
    )
    try:
        raw = complete_json(DISCOVERY_SYSTEM_PROMPT, user_prompt)
        parsed = parse_json_object(raw)
        if not isinstance(parsed, dict):
            return [], _empty_bundle(), "medium"

        candidates_raw = parsed.get("candidate_entities", [])
        candidates: list[CandidateEntity] = []
        for i, c in enumerate(candidates_raw):
            if not isinstance(c, dict):
                continue
            candidates.append(
                CandidateEntity(
                    candidate_id=c.get("candidate_id") or f"cand_{i + 1:02d}",
                    name=c.get("name") or subject.primary_name,
                    country=c.get("country"),
                    industry=c.get("industry"),
                    why_shown=c.get("why_shown") or "Found in discovery search",
                )
            )

        inferred_raw = parsed.get("inferred") or {}
        inferred = SubjectFieldBundle(
            country=inferred_raw.get("country"),
            industry=inferred_raw.get("industry"),
            known_associations=inferred_raw.get("known_associations") or [],
        )
        hint = str(parsed.get("model_ambiguity_hint", "medium")).lower()
        if hint not in ("low", "medium", "high"):
            hint = "medium"
        return candidates, inferred, hint
    except Exception as e:
        logger.warning("Entity discovery LLM failed: %s", e)
        return [], _empty_bundle(), "medium"


def _apply_clarification(
    resolved: ResolvedSubject,
    clarification: ClarificationRequest,
    candidates: list[CandidateEntity],
) -> tuple[ResolvedSubject, CandidateEntity | None]:
    selected: CandidateEntity | None = None
    if clarification.candidate_id:
        for c in candidates:
            if c.candidate_id == clarification.candidate_id:
                selected = c
                break

    country = clarification.country or (selected.country if selected else None)
    industry = clarification.industry or (selected.industry if selected else None)
    associations = list(clarification.known_associations)
    if selected and selected.name and not associations:
        pass

    resolved.confirmed = SubjectFieldBundle(
        country=country if country and country.lower() != "unknown" else None,
        industry=industry if industry and industry.lower() != "unknown" else None,
        known_associations=associations,
    )
    return resolved, selected


async def run_stage1b_async(
    checkpoint1: dict,
    clarification: ClarificationRequest | None = None,
) -> dict:
    settings = get_settings()
    subject = subject_from_dict(checkpoint1["subject"])
    user_provided = _bundle_from_subject(subject)
    clarified = clarification is not None

    resolved = ResolvedSubject(
        user_provided=user_provided,
        inferred=_empty_bundle(),
        confirmed=_empty_bundle(),
    )

    candidates: list[CandidateEntity] = [
        CandidateEntity.model_validate(c)
        for c in checkpoint1.get("prior_candidate_entities", [])
    ]
    model_hint = "medium"

    if not _user_has_identifier(subject) and not clarified:
        serp_items = await discover_candidates(subject.primary_name)
        candidates, inferred, model_hint = await _run_llm_discovery(subject, serp_items)
        resolved.inferred = inferred
    elif clarified:
        prior_inferred = checkpoint1.get("prior_inferred", {})
        if prior_inferred:
            resolved.inferred = SubjectFieldBundle.model_validate(prior_inferred)
        else:
            resolved.inferred = _empty_bundle()

    selected_candidate: CandidateEntity | None = None
    if clarified and clarification:
        resolved, selected_candidate = _apply_clarification(
            resolved, clarification, candidates
        )

    entity_resolution = _compute_ambiguity(
        candidates,
        _user_has_identifier(subject),
        clarified,
        resolved.inferred,
        model_hint,
    )

    # Anti-loop: after clarification, never pause again
    if clarified and entity_resolution.ambiguity_level == "high":
        entity_resolution = EntityResolution(
            ambiguity_level="medium",
            reason_codes=entity_resolution.reason_codes + ["CLARIFIED"],
            action="continue_limited",
        )

    if not settings.clarification_enabled and entity_resolution.action == "clarification_required":
        entity_resolution = EntityResolution(
            ambiguity_level="medium",
            reason_codes=entity_resolution.reason_codes + ["CLARIFICATION_DISABLED"],
            action="continue_limited",
        )

    clarification_form: ClarificationForm | None = None
    if entity_resolution.action == "clarification_required":
        clarification_form = _build_clarification_form(candidates, resolved.inferred)

    effective_subject = _merge_effective_subject(subject, resolved, selected_candidate)
    extra_limitations: list[str] = []
    if entity_resolution.ambiguity_level == "medium":
        extra_limitations.append(
            "Entity resolution confidence is moderate; screening may include weaker entity matches."
        )
    if entity_resolution.action == "continue_limited":
        extra_limitations.append(
            "Limited entity enrichment; open-web coverage may not anchor the subject precisely."
        )

    screening_scope = build_screening_scope(effective_subject, extra_limitations)

    run_id = checkpoint1.get("run_id", "?")
    logger.info(
        "[%s] entity_resolution ambiguity=%s action=%s candidates=%d clarified=%s",
        run_id,
        entity_resolution.ambiguity_level,
        entity_resolution.action,
        len(candidates),
        clarified,
    )

    return {
        "run_id": checkpoint1["run_id"],
        "stage": "entity_resolution",
        "status": "complete",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "subject": effective_subject.model_dump(),
        "screening_scope": screening_scope.model_dump(),
        "search_queries": screening_scope.search_queries,
        "resolved_subject": resolved.model_dump(),
        "entity_resolution": entity_resolution.model_dump(),
        "candidate_entities": [c.model_dump() for c in candidates],
        "clarification_form": clarification_form.model_dump() if clarification_form else None,
        "clarification_received": clarified,
    }


def run_stage1b(
    checkpoint1: dict,
    clarification: ClarificationRequest | None = None,
) -> dict:
    return run_coroutine_sync(run_stage1b_async(checkpoint1, clarification))
