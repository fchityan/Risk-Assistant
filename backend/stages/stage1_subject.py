"""Stage 1: Subject preparation and search query generation."""

import re
from datetime import datetime, timezone

from schemas.report import ScreenRequest, ScreeningScope, Subject

TITLE_PREFIXES = re.compile(
    r"^(mr|mrs|ms|dr|prof|sir|dame)\.?\s+",
    re.IGNORECASE,
)

COUNTRY_JURISDICTION_MAP = {
    "singapore": ["Singapore"],
    "sg": ["Singapore"],
    "malaysia": ["Malaysia", "Singapore"],
    "my": ["Malaysia"],
    "indonesia": ["Indonesia"],
    "id": ["Indonesia"],
    "united states": ["United States"],
    "us": ["United States"],
    "usa": ["United States"],
    "united kingdom": ["United Kingdom"],
    "uk": ["United Kingdom"],
    "china": ["China", "Hong Kong"],
    "cn": ["China"],
    "hong kong": ["Hong Kong", "China"],
    "hk": ["Hong Kong"],
    "australia": ["Australia"],
    "au": ["Australia"],
}

COUNTRY_LANGUAGE_MAP = {
    "singapore": ["en"],
    "sg": ["en"],
    "malaysia": ["en", "ms"],
    "indonesia": ["id", "en"],
    "united states": ["en"],
    "united kingdom": ["en"],
    "china": ["zh", "en"],
    "hong kong": ["en", "zh"],
    "australia": ["en"],
}

ADVERSE_TERMS = "fraud OR corruption OR investigation OR enforcement OR lawsuit OR sanction"
REGULATORY_TERMS = "regulatory enforcement legal action"
SANCTIONS_TERMS = "sanctions OR watchlist OR OFAC"

SITE_CONSTRAINTS = [
    "site:reuters.com",
    "site:straitstimes.com",
    "site:channelnewsasia.com",
]


def normalize_name(name: str) -> str:
    cleaned = name.strip()
    cleaned = TITLE_PREFIXES.sub("", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def _resolve_country_key(country: str | None) -> str | None:
    if not country:
        return None
    return country.strip().lower()


def map_jurisdictions(country: str | None) -> list[str]:
    key = _resolve_country_key(country)
    if key and key in COUNTRY_JURISDICTION_MAP:
        return COUNTRY_JURISDICTION_MAP[key]
    if country:
        return [country.strip()]
    return ["Global"]


def map_languages(country: str | None) -> list[str]:
    key = _resolve_country_key(country)
    if key and key in COUNTRY_LANGUAGE_MAP:
        return COUNTRY_LANGUAGE_MAP[key]
    return ["en"]


def build_subject(req: ScreenRequest) -> Subject:
    return Subject(
        subject_type=req.subject_type,
        primary_name=normalize_name(req.primary_name),
        aliases=[normalize_name(a) for a in req.aliases if a.strip()],
        country=req.country,
        industry=req.industry,
        known_associations=[a.strip() for a in req.known_associations if a.strip()],
        input_notes=req.input_notes,
    )


def subject_from_dict(data: dict) -> Subject:
    return Subject.model_validate(data)


def generate_search_queries(subject: Subject) -> list[str]:
    name = subject.primary_name
    anchor = subject.country or subject.industry or ""
    queries: list[str] = []

    if anchor:
        queries.append(f'"{name}" "{anchor}" {ADVERSE_TERMS}')
    else:
        queries.append(f'"{name}" {ADVERSE_TERMS}')

    queries.append(f'"{name}" {REGULATORY_TERMS}')
    queries.append(f'"{name}" {SANCTIONS_TERMS}')

    for association in subject.known_associations:
        queries.append(f'"{name}" "{association}" {ADVERSE_TERMS}')

    for alias in subject.aliases:
        if alias.lower() != name.lower():
            queries.append(f'"{alias}" {ADVERSE_TERMS}')

    for site in SITE_CONSTRAINTS:
        queries.append(f'"{name}" {site} {ADVERSE_TERMS}')

    seen: set[str] = set()
    unique: list[str] = []
    for q in queries:
        key = q.lower()
        if key not in seen:
            seen.add(key)
            unique.append(q)
    return unique


def build_screening_scope(subject: Subject, extra_limitations: list[str] | None = None) -> ScreeningScope:
    limitations = [
        "Open-web public sources only; subscription databases not searched.",
        "Automated screening; analyst review required for elevated findings.",
    ]
    if extra_limitations:
        limitations.extend(extra_limitations)

    return ScreeningScope(
        jurisdictions=map_jurisdictions(subject.country),
        languages=map_languages(subject.country),
        lookback_period_years=5,
        search_queries=generate_search_queries(subject),
        screening_limitations=limitations,
    )


def run_stage1(run_id: str, req: ScreenRequest) -> dict:
    subject = build_subject(req)
    screening_scope = build_screening_scope(subject)

    return {
        "run_id": run_id,
        "stage": "subject_prep",
        "status": "complete",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "subject": subject.model_dump(),
        "screening_scope": screening_scope.model_dump(),
        "search_queries": screening_scope.search_queries,
    }
