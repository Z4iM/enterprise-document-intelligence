
# EDI — LangGraph Workflow Design

## Objective
Orchestrate existing EDI document and policy services using
LangGraph, with explicit human-review and evidence gates.

## MVP Scope
Input: existing document_id and policy_id.
Output: workflow status, required actions, and policy evidence.

No replacement of the existing upload pipeline in the MVP.

## Nodes

1. load_document
   - Retrieve the stored document.
   - Check processing status and structured data.

2. quality_gate
   - Reject failed or incomplete processing.
   - Route all unreviewed documents (including auto_accepted) to explicit review.
   - Allow fallback only after a validated human correction; retain its extraction method.
   - Reject documents explicitly marked rejected.

3. load_approved_rules
   - Load only source-verified, human-approved rules.
   - Verify source evidence integrity.

4. evaluate_policy
   - Reuse the deterministic rule evaluator.
   - Evaluate the approved rule subset only.

5. route_actions
   - Handle requires_approval.
   - Handle requires_documentation.
   - Handle needs_review.
   - Handle passed with limited policy coverage.

6. finalize
   - Return structured results and source evidence.
   - Preserve the distinction between a requirement
     and its fulfillment.

## Human-in-the-Loop
Documents requiring review must not proceed automatically.
Durable SQLite checkpoints support pause/resume through the local-only
`/workflows/start`, `/workflows/{id}`, and `/workflows/{id}/resume` APIs.
Resume reloads the document; a resume signal is never approval.

## Safety Requirements
- Never let the LLM approve its own extracted data.
- Never silently bypass a human-review requirement.
- Never treat missing rules as proof of compliance.
- Never automatically grant manager approval.
- Keep model extraction separate from policy decisions.
- Preserve evidence for every evaluated approved rule.

## Initial Testing
- Approved document with triggered policy rules.
- Document awaiting review.
- Rejected document.
- Missing approved policy rules.
- Missing or invalid structured data.
- Corrected document eligible for re-evaluation.

## Future Enhancements
- Persistent workflow checkpoints.
- Human-review resume.
- Durable background execution.
- Workflow audit history and idempotency.
- API and frontend integration.
- Arabic/English evaluation and broader benchmarks.
