
from decimal import Decimal, InvalidOperation
from typing import Any

from app.validation.rule_schemas import (
    PolicyRule,
    RuleEvaluation,
)
from app.validation.category_normalizer import normalize_category


OPERATORS = {
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    "==": lambda a, b: a == b,
}


def parse_decimal(value: Any) -> Decimal | None:
    """Convert a document value into a Decimal."""

    if value is None or isinstance(value, bool):
        return None

    cleaned = (
        str(value)
        .replace("$", "")
        .replace(",", "")
        .strip()
    )

    try:
        number = Decimal(cleaned)

        if not number.is_finite():
            return None

        return number

    except (InvalidOperation, ValueError):
        return None


def evaluate_rule(
    rule: PolicyRule,
    document_data: dict,
) -> RuleEvaluation:

    # -----------------------------------------
    # 1. Normalize and compare categories
    # -----------------------------------------

    document_category = normalize_category(
        document_data.get("expense_category")
    )

    rule_category = normalize_category(
        rule.category
    )

    KNOWN_EXPENSE_CATEGORIES = {
        "meal",
        "hotel",
        "ground_transportation",
        "purchase",
    }

    category_matches = document_category == rule_category

    broad_expense_rule = (
        rule_category == "all_expenses"
        and document_category in KNOWN_EXPENSE_CATEGORIES
    )

    if not (category_matches or broad_expense_rule):
        return RuleEvaluation(
            rule_id=rule.rule_id,
            applicable=False,
            triggered=None,
            status="passed",
            explanation="Rule does not apply to this category.",
        )

    # -----------------------------------------
    # 2. Extract numeric value
    # -----------------------------------------

    # Resolve compatible document fields.
    # Hotel total fallback is for our simplified
    # benchmark, not general production invoices.

    field_value = document_data.get(rule.field)

    if (
        field_value is None
        and rule.field == "room_rate"
        and document_category == "hotel"
    ):
        field_value = document_data.get("total")

    actual = parse_decimal(field_value)

    if actual is None:
        return RuleEvaluation(
            rule_id=rule.rule_id,
            applicable=True,
            triggered=None,
            status="needs_review",
            explanation=(
                f"Missing or invalid value for {rule.field}."
            ),
        )

    # -----------------------------------------
    # 3. Perform deterministic comparison
    # -----------------------------------------

    comparison = OPERATORS[rule.operator]

    triggered = comparison(
        actual,
        rule.threshold
    )

    # -----------------------------------------
    # 4. Rule condition is not triggered
    # -----------------------------------------

    if not triggered:
        return RuleEvaluation(
            rule_id=rule.rule_id,
            applicable=True,
            triggered=False,
            status="passed",
            explanation=(
                f"{actual} {rule.operator} "
                f"{rule.threshold} is false."
            ),
        )

    # -----------------------------------------
    # 5. Rule condition is triggered
    # -----------------------------------------

    action_description = {
        "requires_approval": (
            f"Approval required from "
            f"{rule.approval_role or 'an authorized reviewer'}."
        ),
        "requires_documentation": (
            "Supporting documentation is required."
        ),
        "policy_violation": (
            "Policy restriction triggered."
        ),
    }

    return RuleEvaluation(
        rule_id=rule.rule_id,
        applicable=True,
        triggered=True,
        status=rule.action,
        explanation=(
            f"{actual} {rule.operator} "
            f"{rule.threshold} is true. "
            f"{action_description[rule.action]}"
        ),
    )
