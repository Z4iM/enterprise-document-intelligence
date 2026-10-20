
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import (
    PolicyChunk,
    StoredPolicyRule,
)
from app.validation.rule_schemas import PolicyRule
from app.validation.source_verifier import normalize_whitespace


class PolicyRuleIntegrityError(Exception):
    """A stored approved rule has invalid or missing evidence."""


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

        # An approved rule must have an approval record.
        if not stored.approved_by or stored.approved_at is None:
            raise PolicyRuleIntegrityError(
                f"Rule {stored.rule_id} has no approval record."
            )

        # Reconstruct and validate the Pydantic rule.
        try:
            rule = PolicyRule.model_validate(stored.rule_data)
        except ValidationError as error:
            raise PolicyRuleIntegrityError(
                f"Rule {stored.rule_id} contains invalid data."
            ) from error

        if rule.rule_id != stored.rule_id:
            raise PolicyRuleIntegrityError(
                f"Rule ID mismatch for {stored.id}."
            )

        # Every approved rule must reference a real chunk
        # from the same policy.
        chunk = db.get(
            PolicyChunk,
            rule.source_chunk_id,
        )

        if chunk is None or chunk.policy_id != policy_id:
            raise PolicyRuleIntegrityError(
                f"Rule {rule.rule_id} has invalid source evidence."
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
                "or unsupported source quote."
            )

        approved_rules.append(rule)

    return approved_rules
