
from sqlalchemy.orm import Session

from app.agents.tools.document_tools import inspect_document
from app.database.models import PolicyDocument
from app.validation.approved_rule_repository import (
    PolicyRuleIntegrityError,
    load_approved_rules,
)
from app.validation.evaluation_service import evaluate_verified_rules


def evaluate_document_policy(
    document_id: str,
    policy_id: str,
    allowed_document_ids: set[str],
    allowed_policy_ids: set[str],
    db: Session,
) -> dict:
    """
    Evaluate a reviewed document against approved policy rules.

    Security:
    - Read-only operation.
    - Both resources must be authorized.
    - Only reviewed LLM-extracted data is trusted.
    - Only verified, human-approved policy rules are used.
    - The LLM never calculates or overrides policy decisions.
    """

    # Authorization must happen before any database access.
    if (
        document_id not in allowed_document_ids
        or policy_id not in allowed_policy_ids
    ):
        return {"status": "access_denied"}

    # Reuse our existing document quality restrictions.
    document_result = inspect_document(
        document_id=document_id,
        allowed_document_ids=allowed_document_ids,
        db=db,
    )

    if document_result["status"] == "not_found":
        return {
            "status": "not_found",
            "resource": "document",
        }

    if document_result["status"] != "ready":
        return {
            "status": "needs_review",
            "reason": "document_not_verified",
        }

    # Verify the selected policy exists.
    policy = db.get(PolicyDocument, policy_id)

    if policy is None:
        return {
            "status": "not_found",
            "resource": "policy",
        }

    # Load only verified, human-approved, source-backed rules.
    try:
        approved_rules = load_approved_rules(
            db=db,
            policy_id=policy_id,
        )
    except PolicyRuleIntegrityError:
        return {
            "status": "needs_review",
            "reason": "invalid_policy_evidence",
        }

    if not approved_rules:
        return {
            "status": "needs_review",
            "reason": "no_approved_policy_rules",
        }

    # Deterministic evaluation: no LLM call happens here.
    evaluation = evaluate_verified_rules(
        document_data=document_result["structured_data"],
        approved_rules=approved_rules,
    )

    # Preserve source evidence for traceability.
    evidence = [
        {
            "policy_id": policy_id,
            "rule_id": rule.rule_id,
            "source_chunk_id": rule.source_chunk_id,
            "source_quote": rule.source_quote,
        }
        for rule in approved_rules
    ]

    return {
        "status": evaluation["status"],
        "document_id": document_id,
        "policy_id": policy_id,
        "evaluation": evaluation,
        "evidence": evidence,
        "coverage": "approved_rules_only",
        "full_compliance_certified": False,
    }
