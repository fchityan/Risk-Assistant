# AI Readiness & Model Governance Assessment — Risk Assistant

## AI and decision architecture

Risk Assistant is a collaborative prototype using public-source research, entity resolution, LLM-assisted evidence processing and **deterministic rule-based risk outcomes**. A Streamlit review interface works with a FastAPI backend; configurable integrations include Bright Data, Playwright, OpenAI-compatible LLM providers and an optional Daytona sandbox.

**Key boundary:** A language model can assist evidence classification and report wording, but the defined scoring logic should remain reviewable, and final compliance decisions require human judgment.

## Governance controls and gaps

| Control | Repository implementation | Additional verification before commercial use |
|---|---|---|
| Subject identity | Entity-resolution and clarification flow | Independent identity precision and ambiguity testing |
| Source reliability | Source tiers, evidence collection and report links | Coverage checks, permitted-source policy and factual verification |
| LLM outputs | Structured evidence-classification stages | Prompt evaluation, hallucination testing and reviewer agreement |
| Deterministic decisions | Rule-engine and fixed rubric | Risk-owner approval and rules-version governance |
| Traceability | Audit trail and report schema | Retention, access control and data-protection process |
| Human oversight | Analyst review dashboard and clarification | Documented reviewer accountability, appeal and override paths |

## Evidence maturity

The **Top 10 finalist ranking among 55 teams** reflects hackathon recognition, not independently validated screening accuracy, regulatory approval or enterprise-production adoption. Before rollout, define a controlled evaluation set and an analyst UAT protocol.

See [requirements and solution design](../business-analysis/business-requirements-and-solution-design.md).
