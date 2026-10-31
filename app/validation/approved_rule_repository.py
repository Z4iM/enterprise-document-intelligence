
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import (
    PolicyChunk,
    StoredPolicyRule,
)
from app.validation.rule_schemas import PolicyRule
from app.validation.source_verifier import normalize_whitespace, verify_rule


class PolicyRuleIntegrityError(Exception):
    """A stored approved rule has invalid or missing evidence."""

    def __init__(self, message, *, code="invalid_policy_evidence"):
        super().__init__(message)
        self.code = code


def load_approved_rules(
    db: Session,
    policy_id: str,
) -> list[PolicyRule]:
    """
    Load only verified and human-approved rules
    belonging to the requested policy.
    """

    statement = (
        select(StoredPolicyRule)
        .where(
            StoredPolicyRule.policy_id == policy_id,
            StoredPolicyRule.verification_status == "verified",
            StoredPolicyRule.approval_status == "approved",
        )
        .order_by(StoredPolicyRule.rule_id)
    )

    stored_rules = db.scalars(statement).all()

    approved_rules = []

    for stored in stored_rules:

        approved_rules.append(validate_approved_rule(db, stored, policy_id))

    return approved_rules


def validate_approved_rule(db: Session, stored: StoredPolicyRule, policy_id: str) -> PolicyRule:
    """Shared read-only check for approved, verified rules; never changes approval."""
    if stored.policy_id != policy_id or stored.approval_status != "approved" or stored.verification_status != "verified":
        raise PolicyRuleIntegrityError("Rule is outside the approved, verified policy scope.")
    # An approved rule must have an approval record.
    if not stored.approved_by or stored.approved_at is None:
        raise PolicyRuleIntegrityError(
            f"Rule {stored.rule_id} has no approval record.", code="approval_record_missing"
        )

    # Reconstruct and validate the Pydantic rule.
    try:
        rule = PolicyRule.model_validate(stored.rule_data)
    except ValidationError as error:
        raise PolicyRuleIntegrityError(
            f"Rule {stored.rule_id} contains invalid data.", code="approved_rule_schema_invalid"
        ) from error

    if rule.rule_id != stored.rule_id:
        raise PolicyRuleIntegrityError(
            f"Rule ID mismatch for {stored.id}.", code="approved_rule_identity_mismatch"
        )

    # Every approved rule must reference a real chunk
    # from the same policy.
    chunk = db.get(
        PolicyChunk,
        rule.source_chunk_id,
    )

    if chunk is None or chunk.policy_id != policy_id:
        raise PolicyRuleIntegrityError(
            f"Rule {rule.rule_id} has invalid source evidence.", code="policy_source_reference_invalid"
        )

    # Verify that the exact supporting quote still
    # exists in the referenced policy chunk.
    if (
        not rule.source_quote
        or not rule.source_quote.strip()
        or normalize_whitespace(rule.source_quote)
        not in normalize_whitespace(chunk.text)
    ):
        raise PolicyRuleIntegrityError(
            f"Rule {rule.rule_id} has a missing "
            "or unsupported source quote.", code="policy_source_quote_invalid"
        )

    verification = verify_rule(rule, chunk.text)
    if not verification["verified"]:
        code = "policy_source_semantics_invalid"
        if verification.get("reason") in {
            "Unsupported negation, exception or discretionary wording.",
            "Unsupported exception, negation or discretionary wording.",
        }:
            code = "policy_wording_unsupported"
        raise PolicyRuleIntegrityError(f"Rule {rule.rule_id} no longer matches source semantics.", code=code)
    return rule


def approved_rule_health(db: Session, stored: StoredPolicyRule, policy_id: str) -> dict:
    """Current evidence validity is separate from historical approval labels."""
    if stored.approval_status != "approved" or stored.verification_status != "verified":
        return {"status": "not_active", "reason": None}
    try:
        validate_approved_rule(db, stored, policy_id)
    except PolicyRuleIntegrityError as error:
        return {"status": "invalid", "reason": error.code}
    return {"status": "valid", "reason": None}
