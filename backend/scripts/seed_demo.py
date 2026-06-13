"""Seed a demo run for fast replay without live API credits."""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import get_settings
from orchestrator import save_final_report, save_run_status
from stages.stage5_rules import run_stage5

DEMO_RUN_ID = "DEMO-ORION-001"
DEMO_AMBIG_RUN_ID = "DEMO-AMBIG-001"


def write_json(path: Path, data: dict, retries: int = 5) -> None:
    """Write JSON with retries for flaky OneDrive/sync file handles on Windows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2)
    for attempt in range(retries):
        try:
            path.write_text(payload, encoding="utf-8")
            return
        except OSError:
            if attempt == retries - 1:
                raise
            time.sleep(0.25 * (attempt + 1))


def seed_ambig_demo() -> None:
    """Seed a run paused at clarification_required for UI demo."""
    settings = get_settings()
    run_dir = settings.runs_path / DEMO_AMBIG_RUN_ID
    run_dir.mkdir(parents=True, exist_ok=True)

    subject = {
        "subject_type": "organization",
        "primary_name": "Atlas Global",
        "aliases": [],
        "country": None,
        "industry": None,
        "known_associations": [],
        "input_notes": "Demo ambiguous entity — clarification required",
    }

    screening_scope = {
        "jurisdictions": ["Global"],
        "languages": ["en"],
        "lookback_period_years": 5,
        "search_queries": [
            '"Atlas Global" fraud OR corruption OR investigation OR enforcement OR lawsuit OR sanction',
        ],
        "screening_limitations": [
            "Open-web public sources only; subscription databases not searched.",
            "Automated screening; analyst review required for elevated findings.",
        ],
    }

    checkpoint1 = {
        "run_id": DEMO_AMBIG_RUN_ID,
        "stage": "subject_prep",
        "status": "complete",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "subject": subject,
        "screening_scope": screening_scope,
        "search_queries": screening_scope["search_queries"],
    }

    candidate_entities = [
        {
            "candidate_id": "cand_01",
            "name": "Atlas Global Logistics",
            "country": "Singapore",
            "industry": "logistics",
            "why_shown": "SERP match for logistics operator in Southeast Asia",
        },
        {
            "candidate_id": "cand_02",
            "name": "Atlas Global Holdings",
            "country": "United States",
            "industry": "investment",
            "why_shown": "SERP match for US holding company with similar name",
        },
    ]

    clarification_form = {
        "questions": [
            {
                "field": "country",
                "label": "Which country is the subject primarily associated with?",
                "type": "select",
                "options": ["Singapore", "United States", "Other", "Unknown"],
                "required": True,
            },
            {
                "field": "industry",
                "label": "Which industry best matches the subject?",
                "type": "select",
                "options": ["logistics", "investment", "Other", "Unknown"],
                "required": False,
            },
            {
                "field": "known_associations",
                "label": "Any related entity, website, or parent company?",
                "type": "text",
                "options": [],
                "required": False,
            },
        ],
        "candidate_entities": candidate_entities,
    }

    entity_resolution = {
        "ambiguity_level": "high",
        "reason_codes": ["MULTIPLE_PLAUSIBLE_ORGS", "NO_CONFIRMED_COUNTRY"],
        "action": "clarification_required",
    }

    checkpoint1b = {
        "run_id": DEMO_AMBIG_RUN_ID,
        "stage": "entity_resolution",
        "status": "complete",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "subject": subject,
        "screening_scope": screening_scope,
        "search_queries": screening_scope["search_queries"],
        "resolved_subject": {
            "user_provided": {"country": None, "industry": None, "known_associations": []},
            "inferred": {"country": None, "industry": None, "known_associations": []},
            "confirmed": {"country": None, "industry": None, "known_associations": []},
        },
        "entity_resolution": entity_resolution,
        "candidate_entities": candidate_entities,
        "clarification_form": clarification_form,
        "clarification_received": False,
    }

    write_json(run_dir / "checkpoint_subject_prep.json", checkpoint1)
    write_json(run_dir / "checkpoint_entity_resolution.json", checkpoint1b)

    save_run_status(
        DEMO_AMBIG_RUN_ID,
        "clarification_required",
        stage="entity_resolution",
        clarification=clarification_form,
        entity_resolution=entity_resolution,
    )

    print(f"Seeded ambiguous demo run: {DEMO_AMBIG_RUN_ID}")
    print(f"Poll: GET /screen/{DEMO_AMBIG_RUN_ID}")
    print(f"Resume: POST /screen/{DEMO_AMBIG_RUN_ID}/clarify")


def seed() -> None:
    settings = get_settings()
    run_dir = settings.runs_path / DEMO_RUN_ID
    run_dir.mkdir(parents=True, exist_ok=True)

    subject = {
        "subject_type": "organization",
        "primary_name": "Orion Logistics Group",
        "aliases": ["Orion Logistics"],
        "country": "Singapore",
        "industry": "logistics",
        "known_associations": ["Orion Trade Holdings"],
        "input_notes": "Demo seed for hackathon replay",
    }

    screening_scope = {
        "jurisdictions": ["Singapore"],
        "languages": ["en"],
        "lookback_period_years": 5,
        "search_queries": [
            '"Orion Logistics Group" "Singapore" fraud OR corruption OR investigation',
            '"Orion Logistics Group" regulatory enforcement legal action',
        ],
        "screening_limitations": [
            "Open-web public sources only; subscription databases not searched.",
        ],
    }

    checkpoint1 = {
        "run_id": DEMO_RUN_ID,
        "stage": "subject_prep",
        "status": "complete",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "subject": subject,
        "screening_scope": screening_scope,
        "search_queries": screening_scope["search_queries"],
    }

    checkpoint2 = {
        "run_id": DEMO_RUN_ID,
        "stage": "data_collection",
        "status": "complete",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "subject": subject,
        "screening_scope": screening_scope,
        "raw_items": [
            {
                "url": "https://example.com/article",
                "title": "Customs authorities review shipping paperwork at Orion-linked entity",
                "snippet": "Authorities were reported to be reviewing inconsistencies in trade documentation at an Orion-linked operating unit.",
                "full_text": "Authorities were reported to be reviewing inconsistencies in trade documentation at an Orion-linked operating unit linked to Orion Logistics Group in Singapore.",
                "fetch_status": "full",
                "source_domain": "example.com",
                "publication_date": "2025-11-02",
                "query": screening_scope["search_queries"][0],
            },
            {
                "url": "https://example.com/background",
                "title": "Orion Logistics Group expands regional warehousing",
                "snippet": "Orion Logistics Group announced expansion of warehousing capacity in Singapore.",
                "full_text": "Orion Logistics Group announced expansion of warehousing capacity in Singapore with no regulatory issues cited.",
                "fetch_status": "full",
                "source_domain": "example.com",
                "publication_date": "2024-03-15",
                "query": screening_scope["search_queries"][1],
            },
        ],
        "total_queries_run": 2,
        "total_results_fetched": 2,
        "collection_mode": "seeded",
    }

    write_json(run_dir / "checkpoint_subject_prep.json", checkpoint1)
    write_json(run_dir / "checkpoint_data_collection.json", checkpoint2)

    from stages.stage3_sandbox import run_stage3

    checkpoint3 = run_stage3(checkpoint2)
    write_json(run_dir / "checkpoint_sandbox_processing.json", checkpoint3)

    # Hand-crafted LLM classifications for demo (high regulatory finding + low background)
    classifications = []
    for item in checkpoint3["processed_items"]:
        if item["evidence_id"] == "EV-001":
            classifications.append(
                {
                    "evidence_id": "EV-001",
                    "entity_match": "high",
                    "source_tier": "tier_2",
                    "adverse_severity": "high",
                    "recency": "current",
                    "jurisdiction_relevance": "high",
                    "corroboration": "single_source",
                    "case_linkage": "high",
                    "justification": "The entity match is strong due to exact entity naming and jurisdiction alignment. The source reports regulatory review of trade documentation at an Orion-linked unit.",
                    "risk_categories": ["regulatory", "adverse_media"],
                }
            )
        else:
            classifications.append(
                {
                    "evidence_id": item["evidence_id"],
                    "entity_match": "high",
                    "source_tier": "tier_3",
                    "adverse_severity": "low",
                    "recency": "recent",
                    "jurisdiction_relevance": "high",
                    "corroboration": "none",
                    "case_linkage": "low",
                    "justification": "Routine business expansion reporting with no adverse allegations in the excerpt.",
                    "risk_categories": ["other"],
                }
            )

    checkpoint4 = {
        "run_id": DEMO_RUN_ID,
        "stage": "llm_reasoning",
        "status": "complete",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "subject": subject,
        "screening_scope": screening_scope,
        "processed_items": checkpoint3["processed_items"],
        "classifications": classifications,
        "total_sources_reviewed": checkpoint3.get("total_sources_reviewed", 2),
        "items_discarded": checkpoint3.get("items_discarded", 0),
    }
    write_json(run_dir / "checkpoint_llm_reasoning.json", checkpoint4)

    checkpoint5 = run_stage5(checkpoint4)
    write_json(run_dir / "checkpoint_rule_engine.json", checkpoint5)

    save_final_report(DEMO_RUN_ID, checkpoint5["report"])
    save_run_status(DEMO_RUN_ID, "complete", stage="rule_engine")

    print(f"Seeded demo run: {DEMO_RUN_ID}")
    print(f"Poll: GET /screen/{DEMO_RUN_ID}")


if __name__ == "__main__":
    seed()
    seed_ambig_demo()
