
from decimal import Decimal

import pytest

from app.validation.rule_evaluator import evaluate_rule
from app.validation.rule_schemas import PolicyRule


@pytest.mark.parametrize(
    "category, scope, operator, threshold, amount, "
    "action, role, expected_triggered, expected_status",
    [
        (
            "meal", "meal", ">", "100", "$175",
            "requires_approval", "manager",
            True, "requires_approval",
        ),
        (
            "meal", "meal", ">", "100", "$100",
            "requires_approval", "manager",
            False, "passed",
        ),
        (
            "hotel", "hotel", ">", "220", "$250",
            "requires_approval", "director",
            True, "requires_approval",
        ),
        (
            "ground_transportation",
            "ground_transportation", ">", "25", "$30",
            "requires_documentation", None,
            True, "requires_documentation",
        ),
        (
            "meal", "all_expenses", ">=", "25", "$25",
            "requires_documentation", None,
            True, "requires_documentation",
        ),
        (
            "purchase", "purchase", ">", "10000",
            "$12000", "requires_approval", "director",
            True, "requires_approval",
        ),
    ],
)
def test_rule_evaluation(
    category,
    scope,
    operator,
    threshold,
    amount,
    action,
    role,
    expected_triggered,
    expected_status,
):
    rule = PolicyRule(
        rule_id="unit-test-001",
        category=scope,
        field="total",
        operator=operator,
        threshold=Decimal(threshold),
        action=action,
        approval_role=role,
        source_chunk_id="test-chunk",
    )

    document = {
        "expense_category": category,
        "total": amount,
    }

    result = evaluate_rule(
        rule=rule,
        document_data=document,
    )

    assert result.applicable is True
    assert result.triggered == expected_triggered
    assert result.status == expected_status


def test_missing_amount_requires_review():
    rule = PolicyRule(
        rule_id="missing-value-test",
        category="meal",
        field="total",
        operator=">",
        threshold=Decimal(100),
        action="requires_approval",
        approval_role="manager",
        source_chunk_id="test-chunk",
    )

    document = {
        "expense_category": "meal",
    }

    result = evaluate_rule(rule, document)

    assert result.applicable is True
    assert result.triggered is None
    assert result.status == "needs_review"


def test_unrelated_category_is_not_applicable():
    rule = PolicyRule(
        rule_id="category-test",
        category="hotel",
        field="total",
        operator=">",
        threshold=Decimal(220),
        action="requires_approval",
        approval_role="director",
        source_chunk_id="test-chunk",
    )

    document = {
        "expense_category": "meal",
        "total": "$250",
    }

    result = evaluate_rule(rule, document)

    assert result.applicable is False
    assert result.triggered is None
