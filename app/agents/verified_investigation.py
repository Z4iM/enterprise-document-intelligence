
from sqlalchemy.orm import Session

from app.agents.answer_builder import build_evidence_backed_answer
from app.agents.investigation_runner import run_investigation


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
        return {
            "status": "not_ready",
            "reason": official_answer["reason"],
            "tool_trace": investigation.get("tool_trace", []),
        }

    # 4. Return only the evidence-backed answer.
    return {
        "status": "ready",
        "answer": official_answer,
        "tool_trace": investigation.get("tool_trace", []),
    }
