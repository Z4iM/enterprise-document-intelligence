
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.agents.tools.document_tools import inspect_document
from app.database.models import Document


def make_document(**overrides):
    """Create a synthetic document without using the database."""
    data = {
        "id": "doc-001",
        "document_type": "receipt",
        "processing_status": "completed",
        "review_status": "approved",
        "structured_extraction_method": "llm",
        "structured_data": {
            "merchant": "City Cafe",
            "total": "$175.00",
            "expense_category": "meal",
        },
    }

    data.update(overrides)
    return SimpleNamespace(**data)


@pytest.mark.parametrize(
    "review_status",
    ["approved", "corrected"],
)
def test_verified_document_can_be_inspected(review_status):
    db = Mock()
    db.get.return_value = make_document(
        review_status=review_status
    )

    result = inspect_document(
        document_id="doc-001",
        allowed_document_ids={"doc-001"},
        db=db,
    )

    assert result["status"] == "ready"
    assert result["document_type"] == "receipt"
    assert result["structured_data"]["total"] == "$175.00"

    db.get.assert_called_once_with(Document, "doc-001")
    db.add.assert_not_called()
    db.commit.assert_not_called()
    db.delete.assert_not_called()


def test_unauthorized_document_is_blocked():
    db = Mock()

    result = inspect_document(
        document_id="private-document",
        allowed_document_ids={"doc-001"},
        db=db,
    )

    assert result == {"status": "access_denied"}

    # Unauthorized requests must not query the database.
    db.get.assert_not_called()


def test_missing_document_returns_not_found():
    db = Mock()
    db.get.return_value = None

    result = inspect_document(
        document_id="missing-document",
        allowed_document_ids={"missing-document"},
        db=db,
    )

    assert result == {"status": "not_found"}

    db.get.assert_called_once_with(
        Document,
        "missing-document",
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"review_status": "needs_review"},
        {"review_status": "rejected"},
        {"review_status": "auto_accepted"},
        {"processing_status": "failed"},
        {"structured_extraction_method": "regex_fallback"},
        {"structured_data": None},
        {"structured_data": {}},
    ],
)
def test_unverified_data_is_never_exposed(changes):
    db = Mock()
    db.get.return_value = make_document(**changes)

    result = inspect_document(
        document_id="doc-001",
        allowed_document_ids={"doc-001"},
        db=db,
    )

    assert result["status"] == "needs_review"
    assert result["structured_data"] is None

    db.add.assert_not_called()
    db.commit.assert_not_called()
    db.delete.assert_not_called()
