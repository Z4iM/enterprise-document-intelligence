from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.database.models import (
    PolicyChunk,
    PolicyRuleReview,
    StoredPolicyRule,
)
from app.validation.rule_schemas import PolicyRule
from app.validation.source_verifier import (
    normalize_whitespace,
    verify_rule,
)


def review_policy_rule(
    db: Session,
    policy_id: str,
    stored_rule_id: str,
    decision: str,
    reviewer: str,
    notes: str | None = None,
    *,
    commit: bool = True,
) -> dict:
    """Review a candidate rule using an authorized caller."""

    if decision not in {"approve", "reject"}:
        raise ValueError("Decision must be approve or reject.")

    if not reviewer.strip():
        raise ValueError("Reviewer identity is required.")

    stored = db.get(StoredPolicyRule, stored_rule_id)

    if stored is None or stored.policy_id != policy_id:
        raise LookupError("Policy rule not found.")

    if stored.approval_status != "pending":
        raise ValueError("This rule has already been reviewed.")

    if decision == "approve":
        if stored.verification_status != "verified":
            raise ValueError("Only verified rules may be approved.")

        try:
            rule = PolicyRule.model_validate(stored.rule_data)
        except ValidationError as error:
            raise ValueError("Invalid stored rule data.") from error

        if rule.rule_id != stored.rule_id:
            raise ValueError("Stored rule identifier mismatch.")

        chunk = db.get(PolicyChunk, rule.source_chunk_id)

        if chunk is None or chunk.policy_id != policy_id:
            raise ValueError("Policy source evidence is missing.")

        if (
            not rule.source_quote
            or not rule.source_quote.strip()
            or normalize_whitespace(rule.source_quote)
            not in normalize_whitespace(chunk.text)
        ):
            raise ValueError("Source quotation is not supported.")

        verification = verify_rule(rule, chunk.text)

        if not verification["verified"]:
            raise ValueError("Source verification failed: " + verification["reason"])

        values = {
            "approval_status": "approved",
            "approved_by": reviewer,
            "approved_at": datetime.now(UTC),
        }
    else:
        values = {
            "approval_status": "rejected",
            "approved_by": None,
            "approved_at": None,
        }

    # One reviewer wins the pending transition; competing decisions cannot overwrite it.
    changed = db.execute(
        update(StoredPolicyRule)
        .where(
            StoredPolicyRule.id == stored.id,
            StoredPolicyRule.approval_status == "pending",
        )
        .values(**values)
    ).rowcount
    if changed != 1:
        db.rollback()
        raise ValueError("This rule has already been reviewed.")

    review = PolicyRuleReview(
        stored_rule_id=stored.id,
        decision=decision,
        reviewer=reviewer,
        notes=notes,
    )

    db.add(review)
    if commit:
        db.commit()
    else:
        db.flush()
    db.refresh(review)

    return {
        "policy_id": policy_id,
        "rule_id": stored.rule_id,
        "stored_rule_id": stored.id,
        "verification_status": stored.verification_status,
        "approval_status": stored.approval_status,
        "review_id": review.id,
        "reviewer": review.reviewer,
        "decision": review.decision,
    }


def approve_policy_rules(db, policy_id, rule_ids, reviewer):
    """Approve exactly the human-confirmed snapshot, in one all-or-nothing transaction."""
    if not rule_ids or len(rule_ids) > 100 or len(set(rule_ids)) != len(rule_ids):
        raise ValueError("Select 1–100 distinct rules.")
    try:
        results = [review_policy_rule(db, policy_id, identifier, "approve", reviewer,
                                     "Approved in a confirmed batch.", commit=False)
                   for identifier in rule_ids]
        db.commit()
        return {"approved_count": len(results), "rules": results}
    except Exception:
        db.rollback()
        raise
