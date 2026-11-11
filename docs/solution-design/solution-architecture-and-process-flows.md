# Solution Architecture & Process Flows — Risk Assistant

## Executive Summary

This document defines the backend architecture for the public-source reputational screening agent built at the Agent Forge hackathon. The design is intentionally scoped for a one-day build, with production-grade patterns called out where they matter — particularly around auditability, error handling, and the deterministic rubric introduced in the schema design.

The backend runs six sequential stages: subject preparation, **entity resolution (Stage 1.5)**, web data collection, sandbox processing, LLM reasoning, and rule-based assessment. Each stage is isolated, idempotent, and produces a checkpoint, so the pipeline can resume or be replayed from any step — including pausing for analyst clarification when entity identity is ambiguous. The model is responsible only for classification against a fixed rubric; all final risk bands and disposition decisions are computed deterministically in code.[1][2]

Report output conforms to[`schemas/reputation-screening-report-rubric.schema.v1.json` ](../schemas/reputation-screening-report-rubric.schema.v1.json). See[`examples/example-profile.json` ](../examples/example-profile.json) for a trimmed sample.

***

## Architecture Overview

```
┌────────────────────────────────────────────────────────────────────────┐
│  Frontend                                                              │
│  Subject input form → POST /screen → poll GET /screen/{run_id}        │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │  FastAPI Backend              │
                    │  POST /screen                │
                    │  → enqueue run_id            │
                    │  → return {run_id, status}   │
                    └──────────────┬───────────────┘
                                   │ BackgroundTask / async worker
          ┌────────────────────────▼───────────────────────────────┐
          │  Pipeline Orchestrator  (orchestrator.py)               │
          │                                                         │
          │  Stage 1: Subject Prep       → checkpoint_subject_prep.json      │
          │  Stage 1.5: Entity Resolution → checkpoint_entity_resolution.json │
          │  Stage 2: Data Collection    → checkpoint_data_collection.json    │
          │  Stage 3: Sandbox Process    → checkpoint_sandbox_processing.json │
          │  Stage 4: LLM Reasoning      → checkpoint_llm_reasoning.json     │
          │  Stage 5: Rule Engine        → final_report.json                   │
          └─────┬────────────────┬──────────────────┬──────────────┘
                │                │                  │
      ┌─────────▼──┐   ┌─────────▼──┐    ┌──────────▼──────────┐
      │ Bright Data │   │  Daytona   │    │  LLM (TokenRouter /   │
      │ SERP +      │   │  Sandbox   │    │  OpenRouter / Kimi)  │
      │ Browser API │   │  Python SDK│    │  OpenAI-compatible   │
      └────────────┘   └────────────┘    └────────────────────┘
```

The pipeline is exposed over five HTTP endpoints: `GET /health`, `POST /screen`, `GET /screen/{run_id}`, `POST /screen/{run_id}/clarify`, and `POST /screen/{run_id}/memo/sensenova`. The frontend polls `GET /screen/{run_id}` until the run completes, pauses for clarification, or errors.[3][4]

***

## Stage 1 — Subject Preparation

**Responsibility:** Normalize and validate the input, build search queries, derive entity disambiguation context.

**Input:** Raw subject form data from the frontend.

**Output:** A structured `SubjectContext` object and a list of `SearchQuery` objects.

This stage runs entirely in Python with no external calls. It is fast, deterministic, and should never fail unless the input is malformed. It is the place to implement name normalization (stripping titles, handling common aliases), jurisdiction mapping, and the generation of several targeted search queries rather than one vague one.[5][1]

**Query generation strategy:**

Poorly constructed queries are one of the biggest sources of false positives in adverse-media screening. The best tools generate queries that combine multiple attributes to anchor the subject correctly.[6][5]

Generate at minimum:

- `"{name}" "{country OR company OR industry}" fraud OR corruption OR investigation`
- `"{name}" regulatory enforcement legal action`
- `"{name}" "{known association}"` for each known association
- `"{name}" sanctions OR watchlist`

Vary queries across `site:` constraints if relevant (e.g., `site:reuters.com`, `site:straitstimes.com`).

**Checkpoint output (`checkpoint_subject_prep.json`):**

```json
{
  "run_id": "RSR-20260613-001",
  "stage": "subject_prep",
  "status": "complete",
  "subject": { ... },
  "search_queries":["...", "..."],
  "timestamp": "2026-06-13T12:30:00Z"
}
```

***

## Stage 1.5 — Entity Resolution & Clarification Gate

**Responsibility:** Accept minimal subject input (`subject_type` + `primary_name`), infer enrichment fields via a hybrid SERP + LLM discovery pass, score ambiguity deterministically, and pause the pipeline when identity is ambiguous.

**Input:** `checkpoint_subject_prep.json` plus optional analyst `ClarificationRequest` on resume.

**Discovery flow:**

1. Short-circuit to low ambiguity if the user already supplied `country` or `known_associations`, or if a clarification answer is present.
2. Otherwise run lightweight SERP name-search (`discover_candidates`) — 1–2 queries, no Browser fetch.
3. Pass SERP titles/snippets/domains to the configured LLM with a discovery prompt returning `candidate_entities`, inferred `{country, industry, known_associations}`, and an advisory `model_ambiguity_hint`.
4. Apply a deterministic ambiguity rubric (LLM hint is advisory only):
   - **low** — one dominant candidate, or user/clarified identifier present
   - **medium** — best candidate but incomplete secondary attributes
   - **high** — 2+ plausible distinct candidates with no stable secondary identifier
5. On **high** ambiguity (when `CLARIFICATION_ENABLED=true`), set status `clarification_required` and return a structured `clarification_form`. Analyst resumes via `POST /screen/{run_id}/clarify`.

**Reason codes:** `MULTIPLE_PLAUSIBLE_ORGS`, `NO_CONFIRMED_COUNTRY`, `MIXED_NEWS_MATCHES`, `SINGLE_DOMINANT_CANDIDATE`, `USER_PROVIDED_IDENTIFIER`, `NO_ENRICHMENT_FOUND`, `CLARIFIED`.

**Resolved subject traceability:** `resolved_subject` tracks `user_provided`, `inferred`, and `confirmed` field bundles. After resolution, `build_screening_scope()` rebuilds queries from the effective subject (confirmed → inferred → user_provided).

**Anti-loop:** Once a run has a recorded clarification answer, Stage 1.5 will not pause again (ambiguity downgraded to at most medium).

**Graceful degradation:** If SERP or LLM is not configured, entity resolution never hard-blocks — it continues with limited coverage unless the user already supplied an identifier.

**Checkpoint output (`checkpoint_entity_resolution.json`):**

```json
{
  "run_id": "...",
  "stage": "entity_resolution",
  "status": "complete",
  "subject": { "...effective subject..." },
  "screening_scope": { "...rebuilt scope..." },
  "resolved_subject": { "user_provided": {}, "inferred": {}, "confirmed": {} },
  "entity_resolution": {
    "ambiguity_level": "high",
    "reason_codes":["MULTIPLE_PLAUSIBLE_ORGS"],
    "action": "clarification_required"
  },
  "clarification_form": { "questions":[], "candidate_entities":[] }
}
```

Resolution data is an orchestration artifact only — no v1 report schema change. Stage 5 appends an entity-resolution summary to `audit_trail.processing_notes`.

***

## Stage 2 — Web Data Collection (Bright Data)

**Responsibility:** Execute searches and fetch article content. Return raw text items.

**Tools used:** Bright Data SERP API (via `/request` + zone) and **Browser API** (Playwright CDP through `browser_fetch.py`).[7][8]

**Two-call pattern per query:**

1. **SERP call** — submit the search query through the Bright Data request endpoint with your SERP zone; receive organic results (title, URL, snippet, date).[8]
2. **Browser fetch** — for each result above a relevance threshold, fetch the full page via Playwright CDP (Browser API zone credentials).[7]

Fetching everything is wasteful and slow. A practical filter for a hackathon demo: only fetch full content for results where the snippet contains at least one adverse keyword (fraud, investigation, corruption, sanction, regulatory, court, conviction, allegation, lawsuit).[9][7]

**Python sketch (matches `stage2_collect.py`):**

```python
import httpx

BRIGHT_DATA_TOKEN = "..."
REQUEST_URL = "https://api.brightdata.com/request"
SERP_ZONE = "serp_api"

def search_serp(query: str, gl: str = "sg", num_results: int = 10) -> list[dict]:
    google_url = f"https://www.google.com/search?q={query}&gl={gl}&num={num_results}"
    resp = httpx.post(
        REQUEST_URL,
        headers={"Authorization": f"Bearer {BRIGHT_DATA_TOKEN}"},
        json={"zone": SERP_ZONE, "url": google_url, "format": "raw"},
        timeout=60,
    )
    resp.raise_for_status()
    # Parse organic results from response payload
    ...
```

Full-page fetch uses `stages/browser_fetch.py` with `BRIGHT_DATA_BROWSER_USERNAME` / `BRIGHT_DATA_BROWSER_PASSWORD`.

**Error handling:**

Bright Data calls can fail due to rate limits, blocked domains, or timeouts. Wrap each call in a try/except with exponential backoff (max 3 retries). If a fetch fails, retain the SERP snippet as a partial evidence item and flag it with `fetch_status: "snippet_only"`. Do not abort the pipeline over a single failed fetch.[10][1]

**Deduplication:**

SERP results across multiple queries will overlap. Deduplicate by URL before fetching. A `seen_urls` set is sufficient for the hackathon.[5]

**Checkpoint output (`checkpoint_data_collection.json`):**

```json
{
  "run_id": "...",
  "stage": "data_collection",
  "status": "complete",
  "raw_items":[
    {
      "url": "...",
      "title": "...",
      "snippet": "...",
      "full_text": "...",
      "fetch_status": "full | snippet_only | failed",
      "source_domain": "...",
      "publication_date": "..."
    }
  ],
  "total_queries_run": 4,
  "total_results_fetched": 12
}
```

***

## Stage 3 — Sandbox Processing (Daytona)

**Responsibility:** Run text cleaning, entity mention extraction, and source-tier classification inside an isolated sandbox. Return structured candidate evidence items.

**Why use Daytona here?**

Text processing over raw HTML/Markdown can produce large intermediate data structures, and you may want to run programmatic logic that is cleaner and more reproducible in a sandbox than in the main process. Daytona provides OCI/Docker-compatible environments with a dedicated filesystem and network stack per sandbox, sub-90ms creation time, and a Python SDK.[11][12][13]

**Python SDK pattern:**

```python
from daytona_sdk import Daytona, CreateSandboxParams

daytona = Daytona()  # reads DAYTONA_API_KEY from env

def process_in_sandbox(raw_items: list[dict], subject: dict) -> list[dict]:
    sandbox = daytona.create(CreateSandboxParams(language="python"))
    try:
        # Upload the processing script
        sandbox.fs.upload_file("process.py", open("processing/process.py", "rb").read())

        # Upload the data
        import json
        sandbox.fs.upload_file(
            "input_data.json",
            json.dumps({"raw_items": raw_items, "subject": subject}).encode()
        )

        # Execute
        result = sandbox.process.code_run(
            "import subprocess; subprocess.run(['python', 'process.py'])"
        )

        # Download output
        output = sandbox.fs.download_file("processed_items.json")
        return json.loads(output)

    finally:
        daytona.remove(sandbox)
```

**What `process.py` does inside the sandbox:**

1. Load `input_data.json`
2. For each raw item:
   - Strip boilerplate (navigation, footers, ads) using heuristics
   - Extract sentences mentioning the subject name or known associations
   - Classify `source_tier` from domain: Tier 1 = regex match against known regulator/court/major-press domains, Tier 2 = established trade press domains, Tier 3 = all else
   - Flag `is_adverse` based on presence of adverse keyword patterns
   - Truncate content to ≤500 tokens per item to keep LLM context manageable
3. Write `processed_items.json`

**Source-tier domain lists** are loaded from `backend/config/source_tiers.json` (not hardcoded in `process.py`).

**Checkpoint output (`checkpoint_sandbox_processing.json`):**

```json
{
  "run_id": "...",
  "stage": "sandbox_processing",
  "status": "complete",
  "processed_items":[
    {
      "item_id": "EV-001",
      "url": "...",
      "title": "...",
      "source_domain": "...",
      "source_tier": "tier_1 | tier_2 | tier_3",
      "relevant_excerpt": "...",
      "is_adverse": true,
      "adverse_keywords_found":["investigation", "fraud"],
      "publication_date": "..."
    }
  ],
  "items_flagged_adverse": 3,
  "items_retained": 5,
  "items_discarded": 7
}
```

***

## Stage 4 — LLM Reasoning (TokenRouter / OpenRouter / Kimi)

**Responsibility:** Classify each processed evidence item using the defined rubric. The model does NOT determine the overall risk level — that is the rule engine's job.

**Providers:** Configured via `LLM_PROVIDER` in the shared `.env` (root first, `backend/.env` overrides). Default is **TokenRouter** at `https://api.tokenrouter.com/v1` using the OpenAI `chat.completions` API (model `MiniMax-M3`). Alternatives: OpenRouter (`minimax-v3`) or direct Kimi (`moonshot-v1-auto` default).[16][17]

**Batching:** Large evidence sets are classified in batches (default 5 items per call) to avoid truncated JSON responses.

**Critical design principle: constrain the LLM's scope**

The model is asked to do exactly two things per evidence item: assign rubric component values and write a short justification. It does not assign support bands, overall risk levels, or dispositions. Restricting the scope to classification makes structured output more reliable and protects you against the model inventing scores.[18][10]

**System prompt:**

```
You are a compliance screening analyst assistant.
Your task is to classify each evidence item using the provided rubric.
You must output ONLY a valid JSON array. No preamble, no explanation, no markdown.
Classify each item strictly against the rubric definitions provided.
Never invent findings not present in the provided text.
If a component cannot be determined from the text, default to the lowest band.
```

**Per-item classification prompt (one API call per batch of items):**

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://api.moonshot.cn/v1",
    api_key=KIMI_API_KEY
)

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
  recent = published 1–3 years ago
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

def classify_evidence_items(processed_items: list[dict], subject: dict) -> list[dict]:
    items_json = json.dumps(processed_items, indent=2)
    subject_json = json.dumps(subject, indent=2)

    response = client.chat.completions.create(
        model="moonshot-v1-auto",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"""
Subject: {subject_json}

Rubric definitions:
{RUBRIC_DEFINITIONS}

Evidence items to classify:
{items_json}

Return a JSON array, one object per evidence item, each containing:
- evidence_id (from input)
- entity_match (low|medium|high)
- source_tier (tier_1|tier_2|tier_3)
- adverse_severity (low|medium|high|critical)
- recency (stale|recent|current)
- jurisdiction_relevance (low|medium|high)
- corroboration (none|single_source|multi_source)
- case_linkage (low|medium|high)
- justification (1–2 sentences grounded in the excerpt)

Output only the JSON array.
"""
            }
        ],
        temperature=0.1,  # low temperature for consistent classification
        response_format={"type": "json_object"}
    )

    raw = response.choices[0].message.content
    return json.loads(raw)
```

**Output validation with Pydantic:**

After the LLM call, validate every item against your Pydantic schema before passing to the rule engine. Pydantic validation catches schema drift, missing fields, and out-of-enum values from the model output. If an item fails validation, retry once with an explicit error message appended to the prompt, then fall back to a conservative default (lowest bands).[19][20]

```python
from pydantic import BaseModel, validator
from enum import Enum

class EntityMatch(str, Enum):
    low = "low"; medium = "medium"; high = "high"

class SourceTier(str, Enum):
    tier_1 = "tier_1"; tier_2 = "tier_2"; tier_3 = "tier_3"

class AdverseSeverity(str, Enum):
    low = "low"; medium = "medium"; high = "high"; critical = "critical"

class EvidenceRubric(BaseModel):
    evidence_id: str
    entity_match: EntityMatch
    source_tier: SourceTier
    adverse_severity: AdverseSeverity
    recency: str
    jurisdiction_relevance: EntityMatch
    corroboration: str
    case_linkage: EntityMatch
    justification: str
```

**Checkpoint output (`checkpoint_llm_reasoning.json`):**

The rubric classifications, merged back with the processed item metadata. At this stage the JSON schema's `rubric_assessment` block per evidence item is populated.

***

## Stage 5 — Rule Engine (Deterministic Assessment)

**Responsibility:** Compute `support_band` per evidence item and `overall_risk_level`, `recommended_disposition`, and `triggered_rules` for the case. Risk bands and disposition remain fully deterministic — no LLM involvement in scoring.

After assembly, Stage 5 also builds a `dashboard_summary` block (risk category, support counts, entity match score) for the frontend dashboard. When SenseNova is configured, the deterministic memo draft may be polished via LLM; on-demand memo generation is also exposed at `POST /screen/{run_id}/memo/sensenova` (SenseNova first, Kimi fallback).

**Design principle:** The rule engine must be readable as plain English, version-controlled, and independently testable. A judge should be able to read the ruleset and verify that the output is consistent with the inputs without looking at model internals.[21][10][14]

**Evidence support band rules (`RULE_BASED_V1`):**

```python
from dataclasses import dataclass

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

def compute_support_band(r: RubricItem) -> tuple[str, str]:
    """Returns (support_band, rule_id_triggered)."""

    # HIGH support
    if (
        r.entity_match == "high"
        and r.source_tier in ("tier_1", "tier_2")
        and r.adverse_severity in ("high", "critical")
        and r.case_linkage == "high"
        and (r.recency == "current" or r.corroboration == "multi_source")
    ):
        return "high", "EVIDENCE_HIGH_01"

    # HIGH support – official source path (Tier 1 + any severity + direct linkage)
    if (
        r.entity_match in ("medium", "high")
        and r.source_tier == "tier_1"
        and r.adverse_severity in ("high", "critical")
        and r.case_linkage in ("medium", "high")
    ):
        return "high", "EVIDENCE_HIGH_02"

    # MEDIUM support
    medium_hits = sum([
        r.source_tier in ("tier_1", "tier_2"),
        r.recency in ("recent", "current"),
        r.jurisdiction_relevance in ("medium", "high"),
        r.corroboration in ("single_source", "multi_source"),
        r.case_linkage in ("medium", "high"),
    ])
    if (
        r.entity_match in ("medium", "high")
        and r.adverse_severity in ("medium", "high", "critical")
        and medium_hits >= 2
    ):
        return "medium", "EVIDENCE_MEDIUM_01"

    return "low", "EVIDENCE_LOW_01"
```

**Case-level risk and disposition rules:**

```python
MATERIAL_CATEGORIES = {
    "fraud", "financial_crime", "sanctions",
    "regulatory", "corruption", "litigation"
}

def compute_case_risk(
    evidence_items: list[dict],
    rubric_results: list[RubricItem],
    support_bands: dict[str, str]
) -> dict:

    high_count = sum(1 for v in support_bands.values() if v == "high")
    medium_count = sum(1 for v in support_bands.values() if v == "medium")
    tier1_hits = sum(1 for r in rubric_results if r.source_tier == "tier_1" and support_bands[r.evidence_id] in ("high","medium"))
    critical_hits = sum(1 for r in rubric_results if r.adverse_severity == "critical")

    # Count material categories with at least medium support
    material_category_count = len({
        cat
        for item in evidence_items
        for cat in item.get("risk_categories",[])
        if cat in MATERIAL_CATEGORIES
        and support_bands.get(item["item_id"]) in ("medium", "high")
    })

    triggered_rules =[]
    overall_risk = "low"
    disposition = "no_material_concern"

    # HIGH risk
    if critical_hits >= 1 and high_count >= 1:
        overall_risk = "high"
        disposition = "reject_or_hold"
        triggered_rules.append("CASE_HIGH_01: critical adverse signal with high-support evidence")

    elif high_count >= 2 and material_category_count >= 1:
        overall_risk = "high"
        disposition = "reject_or_hold"
        triggered_rules.append("CASE_HIGH_02: two+ high-support items in material categories")

    elif tier1_hits >= 1 and high_count >= 1:
        overall_risk = "high"
        disposition = "reject_or_hold"
        triggered_rules.append("CASE_HIGH_03: tier-1 source high-support finding")

    # MEDIUM risk
    elif (high_count >= 1 or medium_count >= 2) and material_category_count >= 1:
        overall_risk = "medium"
        disposition = "escalate_to_compliance"
        triggered_rules.append("CASE_MEDIUM_01: medium/high-support finding in material category")

    elif medium_count >= 1:
        overall_risk = "medium"
        disposition = "manual_review_recommended"
        triggered_rules.append("CASE_MEDIUM_02: medium-support finding warrants review")

    # LOW risk — coverage check
    else:
        overall_risk = "low"
        disposition = "no_material_concern"
        triggered_rules.append("CASE_LOW_01: no material adverse findings above low-support threshold")

    return {
        "overall_risk_level": overall_risk,
        "recommended_disposition": disposition,
        "determination_basis": {
            "method": "rule_based_v1",
            "support_summary": {
                "high_support_evidence_count": high_count,
                "medium_support_evidence_count": medium_count,
                "low_support_evidence_count": len(support_bands) - high_count - medium_count,
                "material_category_count": material_category_count,
                "official_or_tier_1_hits": tier1_hits
            },
            "triggered_rules": triggered_rules
        }
    }
```

**Final report assembly:** Merge the case-level assessment with evidence items, risk flags (synthesized from high/medium-support items), and the analyst checklist (templated from disposition). Write to `final_report.json` and update the run status to `complete`.

***

## API Endpoints

**Status lifecycle:** `queued` → `running` → `clarification_required` → `running` → `complete` | `error`

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Service health and configured integrations (secret presence, not values) |
| `POST /screen` | Start run (minimal: `subject_type` + `primary_name`) |
| `GET /screen/{run_id}` | Poll status; returns report when complete or clarification form when paused |
| `POST /screen/{run_id}/clarify` | Submit clarification to resume a paused run (409 if not awaiting clarification) |
| `POST /screen/{run_id}/memo/sensenova` | Generate full memo via SenseNova; falls back to Kimi on failure (409 unless run is `complete`) |

```python
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel

app = FastAPI()

class ScreenRequest(BaseModel):
    subject_type: str
    primary_name: str
    country: str | None = None
    industry: str | None = None
    known_associations: list[str] =[]
    input_notes: str | None = None

class ClarificationRequest(BaseModel):
    country: str | None = None
    industry: str | None = None
    known_associations: list[str] =[]
    candidate_id: str | None = None
    notes: str | None = None

@app.post("/screen")
async def create_screening(req: ScreenRequest, background_tasks: BackgroundTasks):
    run_id = generate_run_id()
    save_run_status(run_id, "queued")
    background_tasks.add_task(run_pipeline, run_id, req)
    return {"run_id": run_id, "status": "queued"}

@app.get("/screen/{run_id}")
async def get_screening(run_id: str):
    status = load_run_status(run_id)
    if status["status"] == "complete":
        report = load_final_report(run_id)
        return {"run_id": run_id, "status": "complete", "report": report}
    if status["status"] == "clarification_required":
        return {
            "run_id": run_id,
            "status": "clarification_required",
            "clarification_form": status.get("clarification"),
            "entity_resolution": status.get("entity_resolution"),
        }
    return {"run_id": run_id, "status": status["status"], "stage": status.get("stage")}

@app.post("/screen/{run_id}/clarify")
async def clarify_screening(run_id: str, clarification: ClarificationRequest, background_tasks: BackgroundTasks):
    # 409 if status != clarification_required
    save_run_status(run_id, "running", stage="entity_resolution")
    background_tasks.add_task(resume_pipeline, run_id, clarification)
    return {"run_id": run_id, "status": "running", "stage": "entity_resolution"}
```

For the hackathon, using FastAPI's built-in `BackgroundTasks` is sufficient and eliminates the need for Celery or a task queue. The frontend polls `GET /screen/{run_id}` every 3–5 seconds until status is `complete`, `clarification_required`, or `error`.[4]

***

## Checkpointing and Idempotency

Each stage reads its input from the previous checkpoint file and writes its output before handing off. If a stage fails, the orchestrator retries only that stage, not the full pipeline.[2][22]

```python
async def run_pipeline(run_id: str, subject: dict):
    try:
        cp1 = run_or_load("subject_prep", run_id,
                          lambda: stage_1_subject_prep(subject))
        cp1b = run_or_load("entity_resolution", run_id,
                           lambda: stage_1b_resolve(cp1))
        if cp1b["entity_resolution"]["action"] == "clarification_required":
            save_run_status(run_id, "clarification_required", clarification=cp1b["clarification_form"])
            return
        cp2 = run_or_load("data_collection", run_id,
                          lambda: stage_2_collect(cp1b))
        cp3 = run_or_load("sandbox_processing", run_id,
                          lambda: stage_3_sandbox(cp2))
        cp4 = run_or_load("llm_reasoning", run_id,
                          lambda: stage_4_llm(cp3))
        report = run_or_load("rule_engine", run_id,
                             lambda: stage_5_rules(cp4))
        save_final_report(run_id, report)
        save_run_status(run_id, "complete")
    except Exception as e:
        save_run_status(run_id, "error", error=str(e))

def run_or_load(stage_name: str, run_id: str, fn):
    """If checkpoint exists, load and return it. Otherwise run fn and checkpoint."""
    path = f"runs/{run_id}/checkpoint_{stage_name}.json"
    if os.path.exists(path):
        return json.load(open(path))
    result = fn()
    json.dump(result, open(path, "w"), indent=2)
    return result
```

This pattern ensures that a Bright Data timeout or a Kimi API hiccup does not force you to re-fetch and re-process everything from scratch — critical given hackathon credit constraints.[23][10]

***

## Reliability Patterns

Production multi-stage agent pipelines face a "reliability compounding" problem: if each of five stages has 95% reliability, the end-to-end success rate is 0.95^5 = 77%. For the hackathon, apply these patterns:[10]

| Risk | Pattern | Implementation |
|---|---|---|
| Bright Data fetch timeout | Retry with backoff | 3 retries, 2s/4s/8s backoff[1] |
| Bright Data partial failure | Degrade gracefully | Retain SERP snippet if full fetch fails[10] |
| Kimi output schema mismatch | Pydantic validation + retry | Validate output; retry once with error in prompt[19] |
| Kimi API rate limit | Backoff + checkpoint | Checkpoint before LLM call; resume if interrupted[2] |
| Daytona Sandbox error | Recreate and retry | Sandbox creation is < 90ms; safe to retry[11] |
| Empty evidence set | Graceful completion | Return `low` risk with `coverage: limited` flag; do not error[10] |

A key principle for serial pipelines: run Bright Data queries in parallel (one asyncio task per query), then merge results. This reduces Stage 2 latency significantly without increasing complexity.[10]

***

## File and Folder Layout

```
backend/
├── main.py                  # FastAPI app, endpoints
├── orchestrator.py          # run_pipeline, run_or_load, stage dispatch
├── source_config.py         # Adverse keywords + source tier JSON loader
├── config/
│   ├── source_tiers.json    # Tier 1/2 domain lists for sandbox processing
│   └── rules_v1.json        # Rule metadata (reference)
├── stages/
│   ├── stage1_subject.py    # Subject prep and query generation
│   ├── stage1b_resolve.py   # Entity resolution + clarification gate
│   ├── stage2_collect.py    # Bright Data SERP + Browser API
│   ├── stage3_sandbox.py    # Daytona SDK wrapper (local fallback)
│   ├── stage4_llm.py        # Rubric classification (batched)
│   ├── stage5_rules.py      # Rule engine, deterministic aggregation
│   ├── llm_client.py        # TokenRouter / OpenRouter / Kimi client
│   └── browser_fetch.py     # Playwright page fetch for Browser API
├── processing/
│   └── process.py           # Script uploaded to Daytona Sandbox
├── schemas/
│   ├── rubric.py            # Pydantic enums and rubric types
│   ├── report.py            # Full report Pydantic model
│   └── resolution.py        # Entity resolution / clarification models
├── config.py                # Settings from .env
├── logging_config.py        # Rotating file + stdout logging
├── validate_report.py       # Pydantic + JSON Schema validation
├── scripts/
│   └── seed_demo.py         # Pre-seeded DEMO-* runs for replay
├── runs/
│   └── {run_id}/
│       ├── status.json
│       ├── checkpoint_subject_prep.json
│       ├── checkpoint_entity_resolution.json
│       ├── checkpoint_data_collection.json
│       ├── checkpoint_sandbox_processing.json
│       ├── checkpoint_llm_reasoning.json
│       ├── checkpoint_rule_engine.json
│       └── final_report.json
└── requirements.txt

docs/
├── solution-design/
│   ├── solution-architecture-and-process-flows.md
│   ├── system-integration-and-interface-specification.md
│   └── ui-ux-design-standards.md
├── schemas/
│   └── reputation-screening-report-rubric.schema.v1.json
└── examples/
    └── example-profile.json
```

***

## Configuration and Secrets

There are three layers to manage: your **local dev machine**, the **Daytona workspace** (where you code), and the **deployed sandbox** (where the demo app runs). Each needs a slightly different approach.

### Layer 1 — Local dev (`.env` file + `pydantic-settings`)

Keep a `.env` file that never gets committed (add it to `.gitignore`). Copy from `.env.example` at the repo root. Settings load from **repository root `.env` first**, then `backend/.env` overrides — both backend and frontend use this shared file via `backend/config.py` and `frontend/env_shared.py`.[fastapi.tiangolo](https://fastapi.tiangolo.com/advanced/settings/)

```bash
cp .env.example .env   # never commit .env
```

Key groups:

```bash
# Bright Data (SERP + Browser API)
BRIGHT_DATA_API_KEY=...
BRIGHT_DATA_SERP_ZONE=serp_api
BRIGHT_DATA_BROWSER_USERNAME=...
BRIGHT_DATA_BROWSER_PASSWORD=...

# Daytona (Stage 3 processing + optional deploy)
DAYTONA_API_KEY=...
DAYTONA_SERVER_URL=...          # required for current daytona-sdk
DAYTONA_TARGET=local

# LLM Stage 4 (default: TokenRouter)
LLM_PROVIDER=tokenrouter
TOKENROUTER_API_KEY=...
KIMI_API_KEY=...                # also used for memo fallback

# Stage 5 memo polish (optional)
SENSENOVA_API_KEY=...
SENSENOVA_BASE_URL=https://api.sensenova.cn/compatible-mode/v1
SENSENOVA_MODEL=SenseNova-5

# Frontend (shared in same .env)
BACKEND_URL=http://127.0.0.1:8000
USE_MOCK_DATA=false
POLL_INTERVAL_SECONDS=5
POLL_TIMEOUT_SECONDS=900
```

See `.env.example` for the full list including OpenRouter overrides and Bright Data username auto-build options.

### Layer 2 — Daytona workspace (dev environment secrets)

Use the `daytona env set` CLI to register secrets at the workspace level. These persist across workspace restarts and are injected as environment variables into every container and terminal session — no `.env` file needed in the workspace.[daytona](https://www.daytona.io/dotfiles/using-environmental-variables-in-daytona)

```bash
daytona env set BRIGHT_DATA_API_KEY=... DAYTONA_API_KEY=... TOKENROUTER_API_KEY=...

# Verify
daytona env list
```

This is cleaner than keeping a `.env` file in the workspace because the values are stored by Daytona's server, not on disk in your project directory.[daytona](https://www.daytona.io/dotfiles/using-environmental-variables-in-daytona)

### Layer 3 — Deployed sandbox (injected at process launch)

When you spin up the demo sandbox via the SDK, pass secrets as environment variables directly to `CreateSandboxParams`. This keeps them out of your source files entirely.[developers.openai](https://developers.openai.com/cookbook/examples/agents_sdk/computer_use_with_daytona/computer_use_with_daytona)

```python
import os
from daytona_sdk import Daytona, CreateSandboxParams

daytona = Daytona()

sandbox = daytona.create(CreateSandboxParams(
    language="python",
    public=True,
    env_vars={
        "BRIGHT_DATA_API_KEY": os.environ["BRIGHT_DATA_API_KEY"],
        "TOKENROUTER_API_KEY": os.environ["TOKENROUTER_API_KEY"],
        "LLM_PROVIDER": "tokenrouter",
        "RUNS_DIR": "/app/runs",
        # Note: no DAYTONA_API_KEY here — the sandbox doesn't need to call back to Daytona
    }
))
```

The secrets come from your local env (set via `daytona env set` in Layer 2), so they are never hardcoded in the codebase.[developers.openai](https://developers.openai.com/cookbook/examples/agents_sdk/computer_use_with_daytona/computer_use_with_daytona)

### Summary

| Layer | Method | Why |
|---|---|---|
| Local dev | `.env` + `pydantic-settings` | Type-safe, validated at startup, standard FastAPI pattern |
| Daytona workspace | `daytona env set` CLI | Persisted by Daytona server, not on disk |
| Deployed demo sandbox | `env_vars` in `CreateSandboxParams` | Injected at creation from local env, never in source |
| Shared with teammate | Share `.env` out-of-band (WhatsApp/Telegram DM) | Never commit or paste into chat/docs |

After deploying, hit `GET /health` to confirm the sandbox booted with all secrets correctly injected. The endpoint returns presence flags only — never secret values.

***

## Deploying the FastAPI App in a Daytona Sandbox

Daytona provides built-in preview URLs for any port inside a sandbox — no manual tunneling needed. Any HTTP process listening on ports 1–65535 is reachable via a generated URL in the format `https://{port}-{sandboxId}.{daytonaProxyDomain}`.[daytona](https://www.daytona.io/docs/en/preview/)

**Setting `public: true`** on the sandbox makes that preview URL accessible to your teammate's frontend without any auth header.[daytona](https://www.daytona.io/docs/en/preview/)

This is distinct from Stage 3 sandbox processing (short-lived sandboxes for text cleanup). For the hackathon demo, you can run the entire FastAPI backend inside a long-lived public sandbox so the frontend can call it directly.

```python
from daytona_sdk import Daytona, CreateSandboxParams

daytona = Daytona()

# Create a long-lived sandbox for the demo deployment
sandbox = daytona.create(CreateSandboxParams(
    language="python",
    public=True         # preview URLs are unauthenticated — frontend can hit them directly
))

# Upload your backend files
sandbox.fs.upload_file("main.py", open("backend/main.py", "rb").read())
sandbox.fs.upload_file("requirements.txt", open("backend/requirements.txt", "rb").read())

# Install dependencies
sandbox.process.exec("pip install -r requirements.txt -q")

# Start FastAPI with uvicorn on port 8000 (non-blocking)
sandbox.process.exec(
    "uvicorn main:app --host 0.0.0.0 --port 8000 &",
    timeout=10
)

# Get the public URL for the frontend to call
preview_url = sandbox.get_preview_link(8000)
print(f"Backend URL: {preview_url}")
```

Point the frontend's `BACKEND_URL` at `preview_url`. No CORS proxy, no ngrok, no extra infra.[daytona](https://www.daytona.io/docs/en/preview/)

When injecting secrets for the deployed sandbox, combine this pattern with Layer 3 above — pass `env_vars` in `CreateSandboxParams` rather than uploading a `.env` file.

***

## What to Mock for the Demo

For the hackathon demo, having pre-computed checkpoint files for a known test case means you can present Stage 2 onwards instantly, without depending on live Bright Data credits or Daytona availability. The demo flow then becomes:

1. Live: submit the subject via the frontend.
2. Live: show Stages 1–2 completing (or fast-forward using a pre-populated cache hit).
3. Live: show Stage 4 LLM call completing and producing rubric classifications.
4. Live: show the final report rendered in the frontend.

The `run_or_load` checkpointing pattern already supports this — pre-seeding checkpoint files for a known `run_id` effectively creates a "fast replay" mode without any code changes.[22][2]