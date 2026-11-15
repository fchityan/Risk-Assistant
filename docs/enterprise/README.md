# Reputational Risk Screening — Enterprise Reference Pack

**Document maturity:** Enterprise-style governance/operating **proposal** for the collaborative Risk Assistant hackathon prototype. The project's Top 10 placing among 55 teams is not an assurance of screening precision, regulatory certification or deployment.

| Area | Reference pack | Existing artefact |
|---|---|---|
| Risk-review business requirements and traceability | [Business requirements](business-requirements-and-traceability.md) | [BA / process mapping](../business-analysis/business-requirements-and-solution-design.md) |
| Evidence contracts, components and integrations | [Architecture & data contracts](solution-architecture-and-data-contracts.md) | [Process flows](../solution-design/solution-architecture-and-process-flows.md), [API spec](../solution-design/system-integration-and-interface-specification.md), [JSON Schema](../schemas/reputation-screening-report-rubric.schema.v1.json) |
| Validation, source handling, controls and handover | [Assurance & operations](assurance-security-and-operations.md) | [AI governance](../ai-enablement/ai-readiness-and-model-governance-assessment.md), [UI standards](../solution-design/ui-ux-design-standards.md) |

**System boundary:** LLMs support evidence interpretation and memo wording; deterministic rules govern reference risk bands; a human reviewer remains accountable for any actual compliance decision. Enterprise approval, independent accuracy evidence, regulatory interpretation and production security checks are **not evidenced**.
