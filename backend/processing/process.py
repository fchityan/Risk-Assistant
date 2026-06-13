"""Sandbox text processing script — runs inside Daytona or locally."""

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse

def load_config() -> dict:
    candidates = [
        Path("source_tiers.json"),
        Path(__file__).parent.parent / "config" / "source_tiers.json",
    ]
    for path in candidates:
        if path.exists():
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    return {}


def extract_domain(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def classify_source_tier(domain: str, config: dict) -> str:
    tier_1 = config.get("tier_1_domains", [])
    tier_2 = config.get("tier_2_domains", [])
    for d in tier_1:
        if domain == d or domain.endswith(f".{d}"):
            return "tier_1"
    for d in tier_2:
        if domain == d or domain.endswith(f".{d}"):
            return "tier_2"
    return "tier_3"


def classify_source_type(domain: str, config: dict) -> str:
    registry = config.get("registry_domains", [])
    court = config.get("court_domains", [])
    for d in registry:
        if domain == d or domain.endswith(f".{d}"):
            return "registry"
    for d in court:
        if domain == d or domain.endswith(f".{d}"):
            return "court_record"
    if "blog" in domain:
        return "blog"
    return "news"


def strip_boilerplate(text: str) -> str:
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#") and len(stripped) < 80:
            continue
        if re.match(r"^(menu|navigation|cookie|subscribe|share|follow us)", stripped, re.I):
            continue
        cleaned.append(stripped)
    return "\n".join(cleaned)


def find_adverse_keywords(text: str, keywords: list[str]) -> list[str]:
    lower = text.lower()
    return [kw for kw in keywords if kw in lower]


def extract_relevant_sentences(text: str, subject_names: list[str], max_chars: int = 2000) -> str:
    if not text:
        return ""
    sentences = re.split(r"[.!?]\s+", text)
    relevant = []
    for sentence in sentences:
        lower = sentence.lower()
        if any(name.lower() in lower for name in subject_names if name):
            relevant.append(sentence.strip())
    if relevant:
        excerpt = ". ".join(relevant)
    else:
        excerpt = text[:max_chars]
    return excerpt[:max_chars]


def infer_risk_categories(text: str) -> list[str]:
    lower = text.lower()
    categories: list[str] = []
    mapping = {
        "fraud": ["fraud", "scam", "ponzi"],
        "financial_crime": ["money laundering", "financial crime", "embezzlement"],
        "sanctions": ["sanction", "watchlist", "ofac"],
        "regulatory": ["regulatory", "enforcement", "fine", "penalty", "mas", "sec"],
        "litigation": ["lawsuit", "litigation", "court", "sued", "indictment"],
        "corruption": ["corruption", "bribery", "kickback"],
        "political_exposure": ["political", "government official", "pep"],
        "reputational": ["reputational", "controversy", "negative publicity"],
        "adverse_media": ["adverse", "negative report", "allegation"],
    }
    for category, terms in mapping.items():
        if any(t in lower for t in terms):
            categories.append(category)
    if not categories and any(kw in lower for kw in ["investigation", "allegation"]):
        categories.append("adverse_media")
    return categories or ["other"]


def truncate_tokens(text: str, max_tokens: int = 500) -> str:
    words = text.split()
    if len(words) <= max_tokens:
        return text
    return " ".join(words[:max_tokens])


def make_evidence_id(url: str) -> str:
    digest = hashlib.md5(url.encode(), usedforsecurity=False).hexdigest()[:8].upper()
    return f"EV-{digest}"


def process_items(raw_items: list[dict], subject: dict) -> dict:
    config = load_config()
    adverse_keywords = config.get("adverse_keywords", [])

    subject_names = [subject.get("primary_name", "")]
    subject_names.extend(subject.get("aliases", []))
    subject_names.extend(subject.get("known_associations", []))
    subject_names = [n for n in subject_names if n]

    processed: list[dict] = []
    discarded = 0
    flagged_adverse = 0

    for item in raw_items:
        url = item.get("url", "")
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        full_text = item.get("full_text", "")
        domain = item.get("source_domain") or extract_domain(url)

        content = full_text if full_text else snippet
        cleaned = strip_boilerplate(content)
        excerpt = extract_relevant_sentences(cleaned, subject_names)
        if not excerpt:
            excerpt = snippet or title

        combined_text = f"{title} {excerpt}"
        adverse_found = find_adverse_keywords(combined_text, adverse_keywords)
        is_adverse = len(adverse_found) > 0

        if not excerpt.strip() and not is_adverse:
            discarded += 1
            continue

        if is_adverse:
            flagged_adverse += 1

        source_tier = classify_source_tier(domain, config)
        source_type = classify_source_type(domain, config)
        risk_categories = infer_risk_categories(combined_text)

        processed.append(
            {
                "evidence_id": make_evidence_id(url) if url else f"EV-{len(processed) + 1:03d}",
                "source_type": source_type,
                "source_name": domain or "unknown",
                "title": title or "Untitled",
                "url": url,
                "publication_date": item.get("publication_date"),
                "snippet": truncate_tokens(excerpt),
                "language": "en",
                "risk_categories": risk_categories,
                "source_tier_hint": source_tier,
                "is_adverse": is_adverse,
                "adverse_keywords_found": adverse_found,
                "fetch_status": item.get("fetch_status", "unknown"),
            }
        )

    return {
        "processed_items": processed,
        "items_flagged_adverse": flagged_adverse,
        "items_retained": len(processed),
        "items_discarded": discarded,
    }


def main() -> None:
    input_path = Path("input_data.json")
    output_path = Path("processed_items.json")

    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)

    result = process_items(data.get("raw_items", []), data.get("subject", {}))
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)


if __name__ == "__main__":
    main()
