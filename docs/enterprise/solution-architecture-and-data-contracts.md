# Screening Architecture, Evidence Provenance & Integration Contract

**Status:** Prototype architecture based on documented components; not a certified enterprise integration.

```text
Reviewer subject input (person/organization + context)
 → Stage 1 subject preparation
 → Stage 1.5 entity resolution + clarification gate
 → Stage 2 public-source collection (Bright Data / browser integration)
 → Stage 3 sandboxed evidence processing (optional Daytona)
 → Stage 4 LLM-assisted categorization against schema/rubric
 → Stage 5 deterministic risk rules and disposition
 → versioned JSON report, evidence citations and reviewer UI
 → final compliance decision by authorized human (future workflow)
```

The Streamlit UI communicates with FastAPI; the orchestrator can preserve checkpoints, and the report adapter maps the versioned JSON schema to the UI. See [architecture](../solution-design/solution-architecture-and-process-flows.md) and [API contract](../solution-design/system-integration-and-interface-specification.md).

## Data contracts and integrity
| Record | Minimum reference meaning | Verification / open issue |
|---|---|---|
| Subject intake | Name, person/entity type, distinguishing context | Detect duplicate candidates and ambiguous identity |
| Entity resolution | Selected match and confidence/context | Reviewer confirmation and override history |
| Source evidence | URL, origin, collected time, quoted fact, source tier | Licensing, freshness, immutable excerpt and link integrity |
| Evidence classification | Rubric category, confidence/uncertainty, reason | Compare LLM coding to human-labelled cases |
| Deterministic report | Findings, rule outcome, citations, audit trail | Validate against [v1 JSON schema](../schemas/reputation-screening-report-rubric.schema.v1.json) |
| Analyst decision | Review status, overrides and rationale | **Not established as certified operational system** |

The complete field-level schema is in the linked JSON Schema, not this summary. Demo/example profiles must be clearly labelled and never confused with live verified screening evidence.

## Architecture decisions
- **ADR-RA-01:** Entity-resolution clarification precedes evidence scoring; ambiguous identities must not silently proceed.
- **ADR-RA-02:** LLM outputs are bounded by structured evidence rubric; final reference risk calculation is deterministic.
- **ADR-RA-03:** Preserve sources, checkpoints and report-schema version for auditability and replay.
- **ADR-RA-04:** Provider fallback must be observable; a failed source cannot be represented as a clear search result.
- **ADR-RA-05:** Human reviewer controls final disposition; prototype labels are decision support.

**Integration prerequisites:** source and provider lawful-use review, dependency secrets management, API auth, idempotency and retry semantics, audit/retention policy, regulated-screening scope definition, and change approvals for rubric or model.
