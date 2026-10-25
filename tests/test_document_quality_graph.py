
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.database.models import Document
from app.workflows import document_policy_graph as workflow


def make_document(**overrides):
    """Create an in-memory document for testing."""
    data = {
        "processing_status": "completed",
        "review_status": "auto_accepted",
        "structured_extraction_method": "llm",
        "structured_data": {
            "expense_category": "meal",
            "total": "$175.00",
        },
    }

    data.update(overrides)

    return SimpleNamespace(**data)


@pytest.mark.parametrize(
    (
        "changes",
        "expected_decision",
        "expected_status",
    ),
    [
        (
            {},
            "ready",
            "ready_for_policy_evaluation",
        ),
        (
            {"review_status": "needs_review"},
            "needs_review",
            "needs_review",
        ),
        (
            {"review_status": "rejected"},
            "blocked",
            "blocked",
        ),
        (
            {"processing_status": "failed"},
            "blocked",
            "blocked",
        ),
        (
            {"structured_extraction_method": "regex_fallback"},
            "needs_review",
            "needs_review",
        ),
        (
            {"structured_data": None},
            "needs_review",
            "needs_review",
        ),
    ],
)
def test_document_quality_routing(
    monkeypatch,
    changes,
    expected_decision,
    expected_status,
):
    document = make_document(**changes)

    # Mock the database session.
    session = MagicMock()
    session.get.return_value = document

    context = MagicMock()
    context.__enter__.return_value = session

    monkeypatch.setattr(
        workflow,
        "SessionLocal",
        lambda: context,
    )

    # Execute the REAL compiled LangGraph.
    graph = workflow.build_document_quality_graph()

    result = graph.invoke(
        {
            "document_id": "doc-001",
            "policy_id": "policy-001",
        }
    )

    assert result["decision"] == expected_decision
    assert result["workflow_status"] == expected_status

    session.get.assert_called_once_with(
        Document,
        "doc-001",
    )

    # Quality routing must not modify the database.
    session.add.assert_not_called()
    session.commit.assert_not_called()


def test_missing_document_is_blocked(monkeypatch):
    session = MagicMock()
    session.get.return_value = None

    context = MagicMock()
    context.__enter__.return_value = session

    monkeypatch.setattr(
        workflow,
        "SessionLocal",
        lambda: context,
    )

    graph = workflow.build_document_quality_graph()

    result = graph.invoke(
        {
            "document_id": "missing-document",
            "policy_id": "policy-001",
        }
    )

    assert result["document_found"] is False
    assert result["decision"] == "blocked"
    assert result["workflow_status"] == "blocked"


def test_missing_policy_is_blocked(monkeypatch):
    session = MagicMock()
    session.get.return_value = make_document()

    context = MagicMock()
    context.__enter__.return_value = session

    monkeypatch.setattr(
        workflow,
        "SessionLocal",
        lambda: context,
    )

    graph = workflow.build_document_quality_graph()

    result = graph.invoke(
        {
            "document_id": "doc-001",
        }
    )

    assert result["decision"] == "blocked"
    assert result["reason"] == "No policy was selected."
