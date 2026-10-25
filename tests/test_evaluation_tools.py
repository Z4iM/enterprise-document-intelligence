
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.agents.tools.evaluation_tools import evaluate_document_policy
from app.database.database import Base
from app.database.models import (
    Document,
    PolicyChunk,
    PolicyDocument,
    PolicyValidation,
    StoredPolicyRule,
)
from app.validation.rule_schemas import PolicyRule


@pytest.fixture
def db():
    """Use an isolated in-memory database for every test."""
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    try:
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()


def seed_data(
    db,
    total="$175.00",
    review_status="approved",
    extraction_method="llm",
    processing_status="completed",
    include_policy=True,
    approval_status="approved",
    tampered=False,
):
    """Create a synthetic receipt and two company policy rules."""

    db.add(
        Document(
            id="doc-001",
            original_filename="synthetic_receipt.docx",
            stored_file_path="unused-test-file",
            file_size_bytes=100,
            file_hash="synthetic-document-hash",
            document_type="receipt",
            processing_status=processing_status,
            review_status=review_status,
            structured_extraction_method=extraction_method,
            structured_data={
                "expense_category": "meal",
                "total": total,
            },
        )
    )

    if not include_policy:
        db.commit()
        return

    db.add(
        PolicyDocument(
            id="policy-001",
            original_filename="synthetic_policy.docx",
            stored_file_path="unused-policy-file",
            file_hash="synthetic-policy-hash",
            extracted_text="Synthetic expense reimbursement policy.",
        )
    )

    specifications = [
        (
            "meal-approval",
            "meal",
            ">",
            "100",
            "requires_approval",
            "manager",
            "Meals above $100 require manager approval.",
        ),
        (
            "receipt-documentation",
            "all_expenses",
            ">=",
            "25",
            "requires_documentation",
            None,
            "Expenses of $25 or more require documentation.",
        ),
    ]

    for index, (
        rule_id,
        category,
        operator,
        threshold,
        action,
        approval_role,
        quote,
    ) in enumerate(specifications):

        chunk_id = f"chunk-{rule_id}"

        rule = PolicyRule(
            rule_id=rule_id,
            category=category,
            field="total",
            operator=operator,
            threshold=Decimal(threshold),
            currency="USD",
            action=action,
            approval_role=approval_role,
            source_quote=quote,
            source_chunk_id=chunk_id,
        )

        chunk_text = (
            "Unrelated policy text."
            if tampered and index == 0
            else quote
        )

        db.add(
            PolicyChunk(
                id=chunk_id,
                policy_id="policy-001",
                chunk_index=index,
                text=chunk_text,
            )
        )

        db.add(
            StoredPolicyRule(
                id=f"stored-{rule_id}",
                policy_id="policy-001",
                rule_id=rule_id,
                rule_data=rule.model_dump(mode="json"),
                verification_status="verified",
                approval_status=approval_status,
                approved_by=(
                    "synthetic-reviewer"
                    if approval_status == "approved"
                    else None
                ),
                approved_at=(
                    datetime.now(UTC)
                    if approval_status == "approved"
                    else None
                ),
            )
        )

    db.commit()


def evaluate(db):
    return evaluate_document_policy(
        document_id="doc-001",
        policy_id="policy-001",
        allowed_document_ids={"doc-001"},
        allowed_policy_ids={"policy-001"},
        db=db,
    )


@pytest.mark.parametrize(
    ("allowed_documents", "allowed_policies"),
    [
        (set(), {"policy-001"}),
        ({"doc-001"}, set()),
    ],
)
def test_unauthorized_resources_are_blocked(
    allowed_documents,
    allowed_policies,
):
    db = Mock()

    result = evaluate_document_policy(
        document_id="doc-001",
        policy_id="policy-001",
        allowed_document_ids=allowed_documents,
        allowed_policy_ids=allowed_policies,
        db=db,
    )

    assert result == {"status": "access_denied"}
    db.get.assert_not_called()
    db.execute.assert_not_called()


def test_missing_document(db):
    result = evaluate(db)

    assert result == {
        "status": "not_found",
        "resource": "document",
    }


def test_missing_policy(db):
    seed_data(db, include_policy=False)

    result = evaluate(db)

    assert result == {
        "status": "not_found",
        "resource": "policy",
    }


@pytest.mark.parametrize(
    "review_status",
    ["needs_review", "rejected", "auto_accepted"],
)
def test_unreviewed_documents_are_blocked(db, review_status):
    seed_data(db, review_status=review_status)

    result = evaluate(db)

    assert result["status"] == "needs_review"
    assert result["reason"] == "document_not_verified"


def test_regex_fallback_cannot_bypass_review(db):
    seed_data(db, extraction_method="regex_fallback")

    result = evaluate(db)

    assert result["status"] == "needs_review"
    assert result["reason"] == "document_not_verified"


def test_no_approved_rules_requires_review(db):
    seed_data(db, approval_status="pending")

    result = evaluate(db)

    assert result["status"] == "needs_review"
    assert result["reason"] == "no_approved_policy_rules"


def test_tampered_policy_evidence_is_rejected(db):
    seed_data(db, tampered=True)

    result = evaluate(db)

    assert result["status"] == "needs_review"
    assert result["reason"] == "invalid_policy_evidence"


@pytest.mark.parametrize("review_status", ["approved", "corrected"])
def test_175_dollar_meal_requires_approval_and_documents(
    db,
    review_status,
):
    seed_data(db, review_status=review_status)

    result = evaluate(db)

    assert result["status"] == "requires_approval"
    assert result["coverage"] == "approved_rules_only"
    assert result["full_compliance_certified"] is False

    evaluation = result["evaluation"]

    assert evaluation["rules_evaluated"] == 2

    actions = {
        item["action"]
        for item in evaluation["required_actions"]
    }

    assert actions == {
        "requires_approval",
        "requires_documentation",
    }

    # Both rules must provide source evidence.
    assert len(result["evidence"]) == 2

    for item in result["evidence"]:
        assert item["policy_id"] == "policy-001"
        assert item["source_quote"]
        assert item["source_chunk_id"]

    # This investigation must not write validation records.
    records = db.scalars(select(PolicyValidation)).all()
    assert records == []
    assert not db.new
    assert not db.dirty


@pytest.mark.parametrize(
    ("total", "expected_status", "expected_actions"),
    [
        ("$24.99", "passed", set()),
        (
            "$100.00",
            "requires_documentation",
            {"requires_documentation"},
        ),
        (
            "$100.01",
            "requires_approval",
            {"requires_approval", "requires_documentation"},
        ),
    ],
)
def test_policy_threshold_boundaries(
    db,
    total,
    expected_status,
    expected_actions,
):
    seed_data(db, total=total)

    result = evaluate(db)

    assert result["status"] == expected_status

    actions = {
        item["action"]
        for item in result["evaluation"]["required_actions"]
    }

    assert actions == expected_actions
    assert result["full_compliance_certified"] is False
