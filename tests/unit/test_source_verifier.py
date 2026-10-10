
from decimal import Decimal

import pytest

from app.validation.rule_schemas import PolicyRule
from app.validation.source_verifier import verify_rule


MEAL_POLICY = (
    "Any meal expense above $100 requires "
    "manager approval before reimbursement."
)

RECEIPT_POLICY = (
    "Receipts are required for individual "
    "expenses of $25 or more."
)


def make_meal_rule(**overrides):
    data = {
        "rule_id": "test-meal",
        "category": "meal",
        "field": "total",
        "operator": ">",
        "threshold": Decimal("100"),
        "currency": "USD",
        "action": "requires_approval",
        "approval_role": "manager",
        "source_quote": MEAL_POLICY,
        "source_chunk_id": "test-chunk",
    }

    data.update(overrides)
    return PolicyRule.model_validate(data)


def test_correct_meal_rule():
    rule = make_meal_rule()

    result = verify_rule(rule, MEAL_POLICY)

    assert result["verified"] is True


@pytest.mark.parametrize(
    "overrides,expected_error",
    [
        (
            {"operator": ">="},
            "Operator mismatch",
        ),
        (
            {"threshold": Decimal("150")},
            "Threshold not supported",
        ),
        (
            {
                "action": "requires_documentation",
                "approval_role": None,
            },
            "Action mismatch",
        ),
        (
            {"category": "hotel"},
            "Scope mismatch",
        ),
        (
            {"source_quote": None},
            "Missing source quote",
        ),
        (
            {"source_quote": "Invented policy statement."},
            "Source quote not found",
        ),
        (
            {"approval_role": "director"},
            "Approval role not supported",
        ),
    ],
)
def test_invalid_meal_rules_are_rejected(
    overrides,
    expected_error,
):
    rule = make_meal_rule(**overrides)

    result = verify_rule(rule, MEAL_POLICY)

    assert result["verified"] is False
    assert expected_error in result["reason"]


def test_general_receipt_rule():
    rule = PolicyRule(
        rule_id="receipt-test",
        category="all_expenses",
        field="amount",
        operator=">=",
        threshold=Decimal("25"),
        action="requires_documentation",
        approval_role=None,
        source_quote=RECEIPT_POLICY,
        source_chunk_id="receipt-chunk",
    )

    result = verify_rule(rule, RECEIPT_POLICY)

    assert result["verified"] is True


def test_wrong_receipt_scope_is_rejected():
    rule = PolicyRule(
        rule_id="receipt-test",
        category="purchase",
        field="amount",
        operator=">=",
        threshold=Decimal("25"),
        action="requires_documentation",
        approval_role=None,
        source_quote=RECEIPT_POLICY,
        source_chunk_id="receipt-chunk",
    )

    result = verify_rule(rule, RECEIPT_POLICY)

    assert result["verified"] is False
    assert "Scope mismatch" in result["reason"]
