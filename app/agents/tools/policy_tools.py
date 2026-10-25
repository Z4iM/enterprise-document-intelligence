
from sqlalchemy.orm import Session

from app.database.models import PolicyDocument
from app.validation.approved_rule_repository import (
    PolicyRuleIntegrityError,
    load_approved_rules,
)


def get_policy_evidence(
    policy_id: str,
    allowed_policy_ids: set[str],
    db: Session,
) -> dict:
    """
    Retrieve verified and human-approved policy evidence.

    This tool is read-only. It never approves rules,
    modifies records, or determines overall compliance.

    Allowed policy IDs must come from a trusted caller.
    """

    # 1. Check access BEFORE querying the database.
    if policy_id not in allowed_policy_ids:
        return {"status": "access_denied"}

    # 2. Check that the policy exists.
    policy = db.get(PolicyDocument, policy_id)

    if policy is None:
        return {"status": "not_found"}

    # 3. Use our EXISTING trusted rule repository.
    # It checks verification, human approval,
    # matching policy IDs, and supporting source quotes.
    try:
        rules = load_approved_rules(
            db=db,
            policy_id=policy_id,
        )
    except PolicyRuleIntegrityError:
        return {
            "status": "needs_review",
            "policy_id": policy_id,
            "reason": "approved_policy_evidence_invalid",
            "rules": [],
        }

    # 4. Never claim compliance when no approved
    # policy rules are available.
    if not rules:
        return {
            "status": "needs_review",
            "policy_id": policy_id,
            "reason": "no_approved_rules",
            "rules": [],
        }

    # 5. Return only the approved rules and evidence.
    evidence = [
        {
            "policy_id": policy_id,
            "rule_id": rule.rule_id,
            "category": rule.category,
            "field": rule.field,
            "operator": rule.operator,
            "threshold": str(rule.threshold),
            "currency": rule.currency,
            "action": rule.action,
            "approval_role": rule.approval_role,
            "source_chunk_id": rule.source_chunk_id,
            "source_quote": rule.source_quote,
        }
        for rule in rules
    ]

    return {
        "status": "ready",
        "policy_id": policy_id,
        "rule_count": len(evidence),
        "coverage": "approved_rules_only",
        "rules": evidence,
    }
