
from sqlalchemy.orm import Session

from app.agents.answer_builder import build_evidence_backed_answer
from app.agents.investigation_runner import run_investigation

# Only server-defined codes may cross the public boundary; never raw errors/drafts.
BLOCKER_CODES = frozenset({
    "approval_record_missing", "approved_rule_schema_invalid",
    "approved_rule_identity_mismatch", "policy_source_reference_invalid",
    "policy_source_quote_invalid", "policy_source_semantics_invalid",
    "policy_wording_unsupported", "approved_policy_evidence_invalid",
    "invalid_policy_evidence", "no_approved_rules", "no_approved_policy_rules",
    "document_not_verified",
})
STOP_CODES = {
    "tool_limit_reached": "investigation_tool_limit",
    "model_turn_limit_reached": "investigation_turn_limit",
    "insufficient_evidence": "investigation_no_evaluation",
    "tool_result_too_large": "investigation_evidence_limit",
    "invalid_model_response": "investigation_invalid_response",
    "blocked": "investigation_access_blocked",
}


def run_verified_investigation(
    question: str,
    *,
    client,
    model: str,
    allowed_document_ids: set[str],
    allowed_policy_ids: set[str],
    db: Session,
) -> dict:
    """
    Execute a Gemini investigation and return only
    an evidence-backed, deterministic official answer.

    The Gemini-generated draft is never exposed through
    this interface.

    Permissions must originate from trusted application
    authorization, never from Gemini or user-provided IDs.
    """

    # 1. Run our existing bounded, secure agent.
    investigation = run_investigation(
        question=question,
        client=client,
        model=model,
        allowed_document_ids=allowed_document_ids,
        allowed_policy_ids=allowed_policy_ids,
        db=db,
    )

    # 2. Build an official answer exclusively from
    # the deterministic evaluation and approved evidence.
    official_answer = build_evidence_backed_answer(
        investigation
    )

    # 3. Fail closed when the evidence is insufficient.
    if official_answer["status"] != "ready":
        reason = STOP_CODES.get(investigation.get("status"), official_answer["reason"])
        blocker = investigation.get("reason")
        if investigation.get("status") == "needs_review" and isinstance(blocker, str) and blocker in BLOCKER_CODES:
            reason = blocker
        return {
            "status": "not_ready",
            "reason": reason,
            "tool_trace": investigation.get("tool_trace", []),
        }

    # 4. Return only the evidence-backed answer.
    return {
        "status": "ready",
        "answer": official_answer,
        "tool_trace": investigation.get("tool_trace", []),
    }
