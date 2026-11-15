# Risk-Screening Business Requirements & Traceability

**Status:** Requirements hypothesis / design record for a collaborative prototype; not a signed compliance policy or executed customer UAT.

## Business objective and workflow
Help onboarding/risk analysts structure **public-source reputational evidence**, resolve similarly named subjects and present an auditable screening memo. This is **not** sanctions screening certification, legal due diligence or an automated adverse decision.

**Potential stakeholders:** compliance policy owner, onboarding operations, risk analyst, data protection officer, third-party sourcing/legal, security architect, and engineering team. No accountable enterprise signatories have been recorded.

**Illustrative As-Is:** ad hoc searches, manual source notes, inconsistent subject identification. **Reference To-Be:** subject intake → ambiguity check/clarification → permitted research → evidence classification → deterministic rubric → cited memo/report → analyst verification → human final decision.

**Value hypotheses (unmeasured):** time per completed screening, provenance completeness, reviewer agreement, false-identity-match rate, clarification rate, exception handling time and audit reconstruction effort.

## Requirements traceability
| ID | Priority | Requirement | Existing anchor | Proposed acceptance |
|---|---|---|---|---|
| BR-01 | Must | Distinguish individuals/companies sharing a name before screening | Entity-resolution / clarification stage | Ambiguous subject pauses for human confirmation |
| FR-01 | Must | Preserve source tier, URL, excerpt, collected time and entity linkage | Backend evidence collection and report schema | Sample report has verifiable provenance |
| FR-02 | Must | Separate LLM content extraction from deterministic disposition rules | Stage 4 and Stage 5 reference | Perturbed language output cannot override rubric |
| FR-03 | Must | Present findings and supporting citations to reviewer | Frontend, report adapter | Reviewer can inspect each material claim |
| FR-04 | Should | Support pause, resume, duplicate/idempotent screening run | Orchestrator checkpoint design | Retry does not corrupt report state |
| FR-05 | Should | Expose stable API/schema for external review | System integration spec, v1 report schema | Contract and negative-path tests |
| NFR-01 | Must | Define privacy, retention, access and acceptable source policy | **Not attested as deployed** | Legal/privacy approval and logs inspection |
| NFR-02 | Must | Record analyst decision, override and review ownership | **Formal analyst workflow not evidenced** | Approved UAT with reason codes |
| NFR-03 | Should | Monitor source, provider and LLM availability | Configuration and backend references | Provider-error and fallback drills |

## Approval decisions
Define what public data may be collected and retained; risk taxonomy and threshold; external data/LLM provider terms; entity-resolution tolerance; escalation for unresolved identities; legal jurisdiction and reviewer override. All are pending policy-owner agreement. A hackathon award is **not** business acceptance evidence.
