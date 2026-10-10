
from collections.abc import Sequence

from app.validation.rule_evaluator import evaluate_rule
from app.validation.rule_schemas import PolicyRule


def evaluate_verified_rules(
    document_data: dict,
    approved_rules: Sequence[PolicyRule],
) -> dict:
    """
    Evaluate a document against multiple approved policy rules.

    Important:
    The caller must supply rules that have already passed
    source verification and human approval.
    """

    if not approved_rules:
        return {
            "status": "needs_review",
            "summary": "No approved policy rules were provided.",
            "rules_evaluated": 0,
            "applicable_rules": 0,
            "required_actions": [],
            "rule_results": [],
        }

    # Evaluate every supplied rule using the existing
    # deterministic rule evaluator.
    evaluations = [
        evaluate_rule(rule, document_data)
        for rule in approved_rules
    ]

    applicable = [
        result
        for result in evaluations
        if result.applicable
    ]

    statuses = {
        result.status
        for result in applicable
    }

    # Determine an overall status conservatively.
    # Never treat missing or non-applicable rules
    # as proof that the document is compliant.
    if not applicable:
        overall_status = "needs_review"

    elif "policy_violation" in statuses:
        overall_status = "policy_violation"

    elif "needs_review" in statuses:
        overall_status = "needs_review"

    elif "requires_approval" in statuses:
        overall_status = "requires_approval"

    elif "requires_documentation" in statuses:
        overall_status = "requires_documentation"

    else:
        overall_status = "passed"

    # Preserve all triggered requirements, even when
    # the overall status represents only one of them.
    required_actions = [
        {
            "rule_id": result.rule_id,
            "action": result.status,
            "explanation": result.explanation,
        }
        for result in applicable
        if (
            result.triggered is True
            and result.status in {
                "requires_approval",
                "requires_documentation",
                "policy_violation",
            }
        )
    ]

    return {
        "status": overall_status,
        "summary": (
            f"Evaluated {len(applicable)} applicable rules "
            f"out of {len(evaluations)} supplied rules."
        ),
        "rules_evaluated": len(evaluations),
        "applicable_rules": len(applicable),
        "required_actions": required_actions,
        "rule_results": [
            result.model_dump(mode="json")
            for result in evaluations
        ],
    }
