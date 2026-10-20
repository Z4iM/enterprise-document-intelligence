
import pytest

from app.validation.evaluation_service import evaluate_verified_rules
from app.validation.rule_schemas import RuleEvaluation


def make_result(rule_id, status, applicable=True):
    return RuleEvaluation(
        rule_id=rule_id,
        applicable=applicable,
        triggered=True if applicable else None,
        status=status,
        explanation=f"Result for {rule_id}",
    )


def test_no_rules_requires_review():
    result = evaluate_verified_rules(
        document_data={"expense_category": "meal"},
        approved_rules=[],
    )

    assert result["status"] == "needs_review"
    assert result["rules_evaluated"] == 0


def test_no_applicable_rules_requires_review(monkeypatch):
    monkeypatch.setattr(
        "app.validation.evaluation_service.evaluate_rule",
        lambda rule, data: make_result(
            rule,
            "passed",
            applicable=False,
        ),
    )

    result = evaluate_verified_rules(
        document_data={"expense_category": "meal"},
        approved_rules=["hotel-rule"],
    )

    assert result["status"] == "needs_review"
    assert result["applicable_rules"] == 0


def test_multiple_required_actions_are_preserved(monkeypatch):
    simulated_results = {
        "meal-rule": make_result(
            "meal-rule",
            "requires_approval",
        ),
        "receipt-rule": make_result(
            "receipt-rule",
            "requires_documentation",
        ),
    }

    monkeypatch.setattr(
        "app.validation.evaluation_service.evaluate_rule",
        lambda rule, data: simulated_results[rule],
    )

    result = evaluate_verified_rules(
        document_data={
            "expense_category": "meal",
            "total": "$175",
        },
        approved_rules=["meal-rule", "receipt-rule"],
    )

    assert result["status"] == "requires_approval"
    assert result["applicable_rules"] == 2
    assert len(result["required_actions"]) == 2

    actions = {
        action["action"]
        for action in result["required_actions"]
    }

    assert actions == {
        "requires_approval",
        "requires_documentation",
    }


def test_policy_violation_has_highest_priority(monkeypatch):
    simulated_results = {
        "rule-1": make_result(
            "rule-1",
            "requires_approval",
        ),
        "rule-2": make_result(
            "rule-2",
            "policy_violation",
        ),
    }

    monkeypatch.setattr(
        "app.validation.evaluation_service.evaluate_rule",
        lambda rule, data: simulated_results[rule],
    )

    result = evaluate_verified_rules(
        document_data={"expense_category": "meal"},
        approved_rules=["rule-1", "rule-2"],
    )

    assert result["status"] == "policy_violation"
    assert len(result["required_actions"]) == 2


@pytest.mark.parametrize(
    "individual_status, expected_status",
    [
        ("needs_review", "needs_review"),
        ("requires_documentation", "requires_documentation"),
        ("requires_approval", "requires_approval"),
    ],
)
def test_individual_statuses(
    monkeypatch,
    individual_status,
    expected_status,
):
    monkeypatch.setattr(
        "app.validation.evaluation_service.evaluate_rule",
        lambda rule, data: make_result(
            "test-rule",
            individual_status,
        ),
    )

    result = evaluate_verified_rules(
        document_data={"expense_category": "meal"},
        approved_rules=["test-rule"],
    )

    assert result["status"] == expected_status

def test_real_meal_and_receipt_rules_together():
    from decimal import Decimal

    from app.validation.evaluation_service import (
        evaluate_verified_rules,
    )
    from app.validation.rule_schemas import PolicyRule

    meal_rule = PolicyRule(
        rule_id="MEAL-001",
        category="meal",
        field="total",
        operator=">",
        threshold=Decimal(100),
        currency="USD",
        action="requires_approval",
        approval_role="manager",
        source_quote=(
            "Meal expenses above $100 require manager approval."
        ),
        source_chunk_id="chunk-meals",
    )

    receipt_rule = PolicyRule(
        rule_id="RECEIPT-001",
        category="all_expenses",
        field="total",
        operator=">=",
        threshold=Decimal(25),
        currency="USD",
        action="requires_documentation",
        source_quote=(
            "Expenses of $25 or more require a receipt."
        ),
        source_chunk_id="chunk-receipts",
    )

    document_data = {
        "expense_category": "meal",
        "total": "$175.00",
    }

    result = evaluate_verified_rules(
        document_data=document_data,
        approved_rules=[meal_rule, receipt_rule],
    )

    assert result["status"] == "requires_approval"
    assert result["rules_evaluated"] == 2
    assert result["applicable_rules"] == 2

    assert len(result["required_actions"]) == 2

    actions = {
        action["action"]
        for action in result["required_actions"]
    }

    assert actions == {
        "requires_approval",
        "requires_documentation",
    }

    # Both actual numeric comparisons must trigger.
    assert all(
        rule_result["triggered"] is True
        for rule_result in result["rule_results"]
    )
