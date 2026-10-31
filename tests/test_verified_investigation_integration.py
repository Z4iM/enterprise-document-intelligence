
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from google.genai import types
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.agents.verified_investigation import run_verified_investigation
from app.database.database import Base
from app.database.models import (
    Document,
    PolicyChunk,
    PolicyDocument,
    PolicyValidation,
    StoredPolicyRule,
)
from app.validation.rule_schemas import PolicyRule

DOCUMENT_ID = "synthetic-receipt"
POLICY_ID = "synthetic-policy"


@pytest.fixture
def db():
    """An isolated database, never the real EDI database."""
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    try:
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()


def seed_database(db, review_status="approved"):
    """Create one synthetic receipt and two approved policy rules."""

    db.add(
        Document(
            id=DOCUMENT_ID,
            original_filename="synthetic_receipt.docx",
            stored_file_path="unused-test-path",
            file_size_bytes=100,
            file_hash="synthetic-receipt-hash",
            document_type="receipt",
            processing_status="completed",
            review_status=review_status,
            structured_extraction_method="llm",
            structured_data={
                "merchant": "City Cafe",
                "expense_category": "meal",
                "total": "$175.00 USD",
            },
        )
    )

    db.add(
        PolicyDocument(
            id=POLICY_ID,
            original_filename="synthetic_policy.docx",
            stored_file_path="unused-policy-path",
            file_hash="synthetic-policy-hash",
            extracted_text="Synthetic reimbursement policy.",
        )
    )

    rules = [
        (
            "meal-rule",
            "meal",
            ">",
            "100",
            "requires_approval",
            "manager",
            "Meals above $100 require manager approval.",
        ),
        (
            "receipt-rule",
            "all_expenses",
            ">=",
            "25",
            "requires_documentation",
            None,
            "Expenses of $25 or more require receipts.",
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
    ) in enumerate(rules):
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

        db.add(
            PolicyChunk(
                id=chunk_id,
                policy_id=POLICY_ID,
                chunk_index=index,
                text=quote,
            )
        )

        db.add(
            StoredPolicyRule(
                id=f"stored-{rule_id}",
                policy_id=POLICY_ID,
                rule_id=rule_id,
                rule_data=rule.model_dump(mode="json"),
                verification_status="verified",
                approval_status="approved",
                approved_by="synthetic-reviewer",
                approved_at=datetime.now(UTC),
            )
        )

    db.commit()


def tool_response(name, arguments):
    """Simulate a real Gemini function-call response."""
    part = types.Part.from_function_call(
        name=name,
        args=arguments,
    )

    return SimpleNamespace(
        function_calls=[part.function_call],
        candidates=[
            SimpleNamespace(
                content=types.Content(
                    role="model",
                    parts=[part],
                ),
            )
        ],
        text=None,
    )


def text_response(message):
    return SimpleNamespace(
        function_calls=[],
        candidates=[],
        text=message,
    )


def fake_client(*responses):
    client = Mock()
    client.models.generate_content.side_effect = list(responses)
    return client


def investigate(db, client, allowed_documents=None):
    return run_verified_investigation(
        question="Can I reimburse my $175 meal receipt?",
        client=client,
        model="synthetic-test-model",
        allowed_document_ids=(
            {DOCUMENT_ID}
            if allowed_documents is None
            else allowed_documents
        ),
        allowed_policy_ids={POLICY_ID},
        db=db,
    )


def test_complete_investigation_pipeline(db):
    """
    Test the actual dispatcher, document tool, policy
    tool, evaluator, and verified answer builder.
    """
    seed_database(db)

    client = fake_client(
        tool_response(
            "inspect_document",
            {"document_id": DOCUMENT_ID},
        ),
        tool_response(
            "get_policy_evidence",
            {"policy_id": POLICY_ID},
        ),
        tool_response(
            "evaluate_document_policy",
            {
                "document_id": DOCUMENT_ID,
                "policy_id": POLICY_ID,
            },
        ),
        text_response(
            "Your expense was fully approved and reimbursed!"
        ),
    )

    result = investigate(db, client)

    assert result["status"] == "ready"

    answer = result["answer"]

    assert answer["status"] == "ready"
    assert answer["policy_outcome"] == "requires_approval"
    assert answer["full_compliance_certified"] is False

    requirements = {
        item["requirement"]
        for item in answer["required_actions"]
    }

    assert requirements == {
        "Approval required",
        "Documentation required",
    }

    # The final answer must include policy citations.
    assert len(answer["required_actions"]) == 2

    for action in answer["required_actions"]:
        assert action["source_quote"]
        assert action["source_chunk_id"]

    # The hallucinated model statement must not appear
    # anywhere in the authoritative output.
    assert "fully approved and reimbursed" not in str(result)

    assert [item["tool"] for item in result["tool_trace"]] == [
        "inspect_document",
        "get_policy_evidence",
        "evaluate_document_policy",
    ]

    assert client.models.generate_content.call_count == 4

    # Investigation must not save approval decisions.
    assert db.scalars(select(PolicyValidation)).all() == []
    assert not db.new
    assert not db.dirty


def test_unauthorized_document_stops_pipeline(db):
    seed_database(db)

    client = fake_client(
        tool_response(
            "inspect_document",
            {"document_id": DOCUMENT_ID},
        )
    )

    result = investigate(
        db,
        client,
        allowed_documents={"another-document"},
    )

    assert result["status"] == "not_ready"
    assert result["reason"] == "investigation_access_blocked"

    assert result["tool_trace"][0]["status"] == (
        "access_denied"
    )

    assert "answer" not in result
    assert client.models.generate_content.call_count == 1


def test_unreviewed_document_stops_pipeline(db):
    seed_database(db, review_status="needs_review")

    client = fake_client(
        tool_response(
            "inspect_document",
            {"document_id": DOCUMENT_ID},
        )
    )

    result = investigate(db, client)

    assert result["status"] == "not_ready"
    assert result["tool_trace"][0]["status"] == (
        "needs_review"
    )

    assert "answer" not in result
    assert client.models.generate_content.call_count == 1


def test_tampered_policy_evidence_stops_pipeline(db):
    seed_database(db)

    # Simulate a changed policy source that no longer
    # supports its previously approved rule.
    chunk = db.get(PolicyChunk, "chunk-meal-rule")
    chunk.text = "Unrelated policy text."
    db.commit()

    client = fake_client(
        tool_response(
            "evaluate_document_policy",
            {
                "document_id": DOCUMENT_ID,
                "policy_id": POLICY_ID,
            },
        )
    )

    result = investigate(db, client)

    assert result["status"] == "not_ready"
    assert result["tool_trace"][0]["status"] == (
        "needs_review"
    )

    assert "answer" not in result
    assert client.models.generate_content.call_count == 1


def test_stale_policy_reason_reaches_verified_boundary_without_draft(db):
    seed_database(db)
    stored = db.get(StoredPolicyRule, "stored-meal-rule")
    quote = "Meals above $100 may require manager approval."
    stored.rule_data = {**stored.rule_data, "source_quote": quote}
    db.get(PolicyChunk, "chunk-meal-rule").text = quote
    db.commit()
    client = fake_client(tool_response("get_policy_evidence", {"policy_id": POLICY_ID}))
    result = investigate(db, client)
    assert result["status"] == "not_ready"
    assert result["reason"] == "policy_wording_unsupported"
    assert "answer" not in result and "model_draft_unverified" not in result
    assert client.models.generate_content.call_count == 1


def test_unrecognized_blocker_never_exposes_raw_errors(db, monkeypatch):
    import app.agents.verified_investigation as verified

    monkeypatch.setattr(verified, "run_investigation", lambda **kwargs: {
        "status": "needs_review", "reason": "synthetic-private-error-detail", "tool_trace": [],
        "model_draft_unverified": "synthetic-private-draft",
    })
    result = investigate(db, Mock())
    assert result == {"status": "not_ready", "reason": "investigation_incomplete", "tool_trace": []}


@pytest.mark.parametrize(("status", "reason"), [
    ("tool_limit_reached", "investigation_tool_limit"),
    ("model_turn_limit_reached", "investigation_turn_limit"),
    ("insufficient_evidence", "investigation_no_evaluation"),
    ("tool_result_too_large", "investigation_evidence_limit"),
    ("invalid_model_response", "investigation_invalid_response"),
])
def test_bounded_investigation_stops_have_specific_safe_reasons(db, monkeypatch, status, reason):
    import app.agents.verified_investigation as verified

    monkeypatch.setattr(verified, "run_investigation", lambda **kwargs: {
        "status": status, "tool_trace": [], "model_draft_unverified": "synthetic-private-draft",
    })
    result = investigate(db, Mock())
    assert result == {"status": "not_ready", "reason": reason, "tool_trace": []}
