
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.database.models import Document, PolicyDocument
from app.validation.approved_rule_repository import PolicyRuleIntegrityError
from app.validation.rule_schemas import PolicyRule
from app.workflows import document_policy_graph as workflow


@pytest.fixture
def fake_db(monkeypatch):
    session = MagicMock()

    context = MagicMock()
    context.__enter__.return_value = session

    monkeypatch.setattr(
        workflow,
        "SessionLocal",
        lambda: context,
    )

    return session


def make_document(review_status="approved"):
    return SimpleNamespace(
        processing_status="completed",
        review_status=review_status,
        structured_extraction_method="llm",
        structured_data={
            "expense_category": "meal",
            "total": "$175.00",
        },
    )


def make_rules():
    return [
        PolicyRule(
            rule_id="meal-approval",
            category="meal",
            field="total",
            operator=">",
            threshold=Decimal("100.00"),
            currency="USD",
            action="requires_approval",
            approval_role="manager",
            source_quote="Meals above $100 require approval.",
            source_chunk_id="chunk-001",
        ),
        PolicyRule(
            rule_id="expense-documentation",
            category="all_expenses",
            field="total",
            operator=">=",
            threshold=Decimal("25.00"),
            currency="USD",
            action="requires_documentation",
            source_quote="Expenses >= $25 require documentation.",
            source_chunk_id="chunk-002",
        ),
    ]


def configure_documents(session, document):
    def get_record(model, record_id):
        if model is Document:
            return document

        if model is PolicyDocument:
            return SimpleNamespace(id=record_id)

        raise AssertionError("Unexpected database model")

    session.get.side_effect = get_record


def run_graph():
    graph = workflow.build_document_policy_graph()

    return graph.invoke(
        {
            "document_id": "doc-001",
            "policy_id": "policy-001",
        }
    )


def test_approved_receipt_triggers_both_rules(
    fake_db,
    monkeypatch,
):
    configure_documents(fake_db, make_document())

    monkeypatch.setattr(
        workflow,
        "load_approved_rules",
        lambda db, policy_id: make_rules(),
    )

    result = run_graph()

    assert result["decision"] == "ready"
    assert result["workflow_status"] == "requires_approval"

    evaluation = result["policy_evaluation"]

    assert evaluation["rules_evaluated"] == 2
    assert evaluation["applicable_rules"] == 2

    actions = {
        item["action"]
        for item in evaluation["required_actions"]
    }

    assert actions == {
        "requires_approval",
        "requires_documentation",
    }

    evidence = result["policy_evidence"]

    assert len(evidence) == 2
    assert evidence[0]["chunk_id"] == "chunk-001"
    assert evidence[1]["chunk_id"] == "chunk-002"

    fake_db.add.assert_not_called()
    fake_db.commit.assert_not_called()


def test_pending_review_cannot_reach_policy_engine(
    fake_db,
    monkeypatch,
):
    configure_documents(
        fake_db,
        make_document(review_status="needs_review"),
    )

    def forbidden_rule_loading(*args, **kwargs):
        raise AssertionError(
            "Policy engine must not run before human review."
        )

    monkeypatch.setattr(
        workflow,
        "load_approved_rules",
        forbidden_rule_loading,
    )

    result = run_graph()

    assert result["decision"] == "needs_review"
    assert result["workflow_status"] == "needs_review"
    assert "policy_evaluation" not in result

    # The policy record must never be queried.
    fake_db.get.assert_called_once_with(
        Document,
        "doc-001",
    )


def test_no_approved_rules_requires_review(
    fake_db,
    monkeypatch,
):
    configure_documents(fake_db, make_document())

    monkeypatch.setattr(
        workflow,
        "load_approved_rules",
        lambda db, policy_id: [],
    )

    result = run_graph()

    assert result["workflow_status"] == "needs_review"
    assert result["policy_evaluation"]["rules_evaluated"] == 0
    assert result["policy_evaluation"]["required_actions"] == []
    assert result["policy_evidence"] == []


def test_invalid_policy_evidence_requires_review(
    fake_db,
    monkeypatch,
):
    configure_documents(fake_db, make_document())

    def invalid_rules(*args, **kwargs):
        raise PolicyRuleIntegrityError(
            "Supporting policy evidence is invalid."
        )

    monkeypatch.setattr(
        workflow,
        "load_approved_rules",
        invalid_rules,
    )

    result = run_graph()

    assert result["workflow_status"] == "needs_review"
    assert result["reason"] == (
        "Approved policy evidence requires review."
    )
    assert "policy_evaluation" not in result
