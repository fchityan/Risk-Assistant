# Screening QA, AI Governance, Security & Service Readiness

**Evidence classification:** Demo prototype, architecture, report schemas and hackathon recognition are documented. **Not evidenced:** measured identity precision, regulatory certification, formal customer UAT, 24/7 operating service or independent security assessment.

## QA and reviewer acceptance
| Assurance gate | Test case | Evidence required |
|---|---|---|
| Identity | Common name, multiple entities, wrong country, no confident match | Pause/escalation and measured false-match rate |
| Source quality | Broken/paid/duplicated/stale page, conflicting accounts | Tiered provenance, coverage and reviewer review |
| LLM reliability | Fabricated fact, missing citation, schema mismatch, prompt injection | Adversarial suite, error budget and output rejection |
| Rule integrity | Same validated evidence yields same rubric result | Deterministic rule fixtures and version change approval |
| API/frontend | Run/retry/resume, error, auth failure, network timeout, mock mode | Versioned schema integration tests |
| Reviewer UAT | Inspect evidence, correct match, override, reason and approval | Signed reviewer scenario record |
| Security/privacy | PII minimization, session isolation, secrets, retention, provider data handling | DPIA/legal, access and dependency test reports |
| Operations | Provider outage, rate limit, rollback and alert routing | Observed drill with accountable owner |

## Risk register
| Risk | Impact | Proposed control |
|---|---|---|
| Homonym mismatch | Defamatory or misleading report | Clarification gate; human corroboration; block unresolved |
| Hallucinated or misquoted public source | Unfair risk assessment | Citation validation; structured schema; reviewer checks |
| Prompt injection from collected web content | Output hijacking or data leakage | Isolate untrusted text, strict instructions/schema, secret isolation |
| Incomplete search represented as 'no findings' | False clearance | Explicit coverage/error state and stop decision |
| Unlawful use or retention of personal data | Regulatory/privacy exposure | Source approval, minimisation, retention, DSR process |
| Rubric/model/provider change | Inconsistent decisions | Versioned rule approvals, regression set, rollback |

## Security and operations design
**Proposed security gates:** authorize data-source use, MFA/role-based access, API authentication, TLS and network egress allowlist, secret manager, provider-use assessment, scoped logs, encryption at rest and safe deletion. Protect production from mock-data fallback without prominent disclosure.

**Proposed ownership:** Compliance policy owner approves rubric, analyst lead reviews results, source/data owner manages provenance, AI assurance owner tests prompts/rules, privacy/legal approves data flows, platform owner handles service/incident response. No signed enterprise RACI exists.

**Incident handling:** stop affected screening; suspend/adversarially review provider response; preserve approved immutable evidence; restore previous known-good rule and model configuration; re-screen affected records; notify risk/privacy owners; document remediation and change approval.

**Exit gate for any pilot:** legal/privacy clearance, measured entity matching, source coverage validation, adversarial LLM suite, analyst UAT, rule-owner approval, secure deployment tests, operational support and escalation matrix. The Top 10/55 team finish should remain a hackathon outcome only.
