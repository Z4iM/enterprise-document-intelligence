from decimal import Decimal

import pytest

from app.validation.evaluation_service import evaluate_verified_rules
from app.validation.rule_schemas import PolicyRule


def sample_rules():
    """Synthetic rules for isolated policy-engine testing."""
    return [
        PolicyRule(
            rule_id="test-meal-approval",
            category="meal",
            field="total",
            operator=">",
            threshold=Decimal("100.00"),
            currency="USD",
            action="requires_approval",
            approval_role="manager",
            source_quote="Meals above $100 require manager approval.",
            source_chunk_id="synthetic-meals",
        ),
        PolicyRule(
            rule_id="test-documentation",
            category="all_expenses",
            field="total",
            operator=">=",
            threshold=Decimal("25.00"),
            currency="USD",
            action="requires_documentation",
            source_quote="Expenses of $25 or more require documentation.",
            source_chunk_id="synthetic-documentation",
        ),
    ]


def evaluate_meal(total):
    return evaluate_verified_rules(
        document_data={
            "expense_category": "meal",
            "total": total,
        },
        approved_rules=sample_rules(),
    )


def get_actions(result):
    return {
        item["action"]
        for item in result["required_actions"]
    }


def test_meal_below_approval_threshold():
    result = evaluate_meal("$75.00")

    assert result["status"] == "requires_documentation"
    assert result["rules_evaluated"] == 2
    assert get_actions(result) == {"requires_documentation"}

    decisions = {
        item["rule_id"]: item
        for item in result["rule_results"]
    }

    assert decisions["test-meal-approval"]["triggered"] is False
    assert decisions["test-documentation"]["triggered"] is True


def test_missing_total_requires_review():
    result = evaluate_meal(None)

    assert result["status"] == "needs_review"
    assert result["applicable_rules"] == 2
    assert result["required_actions"] == []

    for rule in result["rule_results"]:
        assert rule["status"] == "needs_review"
        assert rule["triggered"] is None


def test_unsupported_currency_requires_review():
    result = evaluate_meal("175.00 EUR")

    assert result["status"] == "needs_review"
    assert result["required_actions"] == []

    for rule in result["rule_results"]:
        assert rule["status"] == "needs_review"
        assert rule["triggered"] is None

@pytest.mark.parametrize(
    (
        "total",
        "expected_status",
        "expected_actions",
        "approval_triggered",
        "documentation_triggered",
    ),
    [
        ("$24.99", "passed", set(), False, False),
        (
            "$25.00",
            "requires_documentation",
            {"requires_documentation"},
            False,
            True,
        ),
        (
            "$100.00",
            "requires_documentation",
            {"requires_documentation"},
            False,
            True,
        ),
        (
            "$100.01",
            "requires_approval",
            {"requires_approval", "requires_documentation"},
            True,
            True,
        ),
    ],
)
def test_policy_threshold_boundaries(
    total,
    expected_status,
    expected_actions,
    approval_triggered,
    documentation_triggered,
):
    result = evaluate_meal(total)

    assert result["status"] == expected_status
    assert get_actions(result) == expected_actions
    assert result["rules_evaluated"] == 2
    assert result["applicable_rules"] == 2

    decisions = {
        item["rule_id"]: item
        for item in result["rule_results"]
    }

    assert (
        decisions["test-meal-approval"]["triggered"]
        is approval_triggered
    )

    assert (
        decisions["test-documentation"]["triggered"]
        is documentation_triggered
    )
