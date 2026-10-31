
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.agents.tools.policy_tools import get_policy_evidence
from app.database.database import Base
from app.database.models import (
    PolicyChunk,
    PolicyDocument,
    StoredPolicyRule,
)
from app.validation.rule_schemas import PolicyRule

POLICY_QUOTE = (
    "Meals above $100 require manager approval."
)


@pytest.fixture
def db():
    """Create an isolated, temporary SQLite database."""
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    try:
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()


def add_policy(db, policy_id="policy-001"):
    db.add(
        PolicyDocument(
            id=policy_id,
            original_filename="synthetic_policy.docx",
            stored_file_path="unused-test-file",
            file_hash=f"synthetic-hash-{policy_id}",
            extracted_text=POLICY_QUOTE,
        )
    )
    db.commit()


def add_rule(
    db,
    rule_id="rule-001",
    policy_id="policy-001",
    approval_status="approved",
    verification_status="verified",
    chunk_text=POLICY_QUOTE,
    chunk_policy_id=None,
    approved_by="synthetic-reviewer",
):
    """Create a rule and its source chunk."""

    chunk_id = f"chunk-{rule_id}"

    rule = PolicyRule(
        rule_id=rule_id,
        category="meal",
        field="total",
        operator=">",
        threshold=Decimal(100),
        currency="USD",
        action="requires_approval",
        approval_role="manager",
        source_quote=POLICY_QUOTE,
        source_chunk_id=chunk_id,
    )

    db.add(
        PolicyChunk(
            id=chunk_id,
            policy_id=chunk_policy_id or policy_id,
            chunk_index=0,
            text=chunk_text,
        )
    )

    db.add(
        StoredPolicyRule(
            id=f"stored-{rule_id}",
            policy_id=policy_id,
            rule_id=rule_id,
            rule_data=rule.model_dump(mode="json"),
            verification_status=verification_status,
            approval_status=approval_status,
            approved_by=(
                approved_by
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


def test_unauthorized_policy_is_blocked():
    db = Mock()

    result = get_policy_evidence(
        policy_id="private-policy",
        allowed_policy_ids={"policy-001"},
        db=db,
    )

    assert result == {"status": "access_denied"}

    # Authorization happens before database access.
    db.get.assert_not_called()
    db.execute.assert_not_called()


def test_missing_policy_returns_not_found(db):
    result = get_policy_evidence(
        policy_id="missing-policy",
        allowed_policy_ids={"missing-policy"},
        db=db,
    )

    assert result == {"status": "not_found"}


def test_approved_policy_evidence_is_returned(db):
    add_policy(db)
    add_rule(db)

    result = get_policy_evidence(
        policy_id="policy-001",
        allowed_policy_ids={"policy-001"},
        db=db,
    )

    assert result["status"] == "ready"
    assert result["rule_count"] == 1
    assert result["coverage"] == "approved_rules_only"

    evidence = result["rules"][0]

    assert evidence["rule_id"] == "rule-001"
    assert evidence["source_quote"] == POLICY_QUOTE
    assert evidence["source_chunk_id"] == "chunk-rule-001"
    assert evidence["threshold"] == "100"
    assert evidence["action"] == "requires_approval"


def test_pending_rule_is_not_exposed(db):
    add_policy(db)
    add_rule(
        db,
        approval_status="pending",
    )

    result = get_policy_evidence(
        policy_id="policy-001",
        allowed_policy_ids={"policy-001"},
        db=db,
    )

    assert result["status"] == "needs_review"
    assert result["reason"] == "no_approved_rules"
    assert result["rules"] == []


def test_only_approved_rules_are_returned(db):
    add_policy(db)

    add_rule(
        db,
        rule_id="approved-rule",
    )

    add_rule(
        db,
        rule_id="pending-rule",
        approval_status="pending",
    )

    result = get_policy_evidence(
        policy_id="policy-001",
        allowed_policy_ids={"policy-001"},
        db=db,
    )

    assert result["status"] == "ready"
    assert result["rule_count"] == 1
    assert result["rules"][0]["rule_id"] == "approved-rule"


def test_tampered_source_quote_requires_review(db):
    add_policy(db)

    add_rule(
        db,
        chunk_text="This text does not contain the policy rule.",
    )

    result = get_policy_evidence(
        policy_id="policy-001",
        allowed_policy_ids={"policy-001"},
        db=db,
    )

    assert result["status"] == "needs_review"
    assert result["reason"] == "approved_policy_evidence_invalid"
    assert result["rules"] == []


def test_missing_approval_record_requires_review(db):
    add_policy(db)

    add_rule(
        db,
        approved_by=None,
    )

    result = get_policy_evidence(
        policy_id="policy-001",
        allowed_policy_ids={"policy-001"},
        db=db,
    )

    assert result["status"] == "needs_review"
    assert result["rules"] == []


def test_wrong_policy_source_chunk_is_rejected(db):
    add_policy(db, "policy-001")
    add_policy(db, "policy-002")

    add_rule(
        db,
        policy_id="policy-001",
        chunk_policy_id="policy-002",
    )

    result = get_policy_evidence(
        policy_id="policy-001",
        allowed_policy_ids={"policy-001"},
        db=db,
    )

    assert result["status"] == "needs_review"
    assert result["rules"] == []


@pytest.mark.parametrize("language", ["en", "ar"])
def test_rule_list_flags_stale_approval_without_changing_it(db, monkeypatch, language):
    from app import main
    from app.validation.approved_rule_repository import (
        PolicyRuleIntegrityError,
        load_approved_rules,
    )

    add_policy(db)
    add_rule(db)
    stored = db.get(StoredPolicyRule, "stored-rule-001")
    quote = (
        "Meals above $100 may require manager approval."
        if language == "en"
        else "مصروفات الوجبات التي تتجاوز ١٠٠ جنيه مصري قد تتطلب موافقة المدير."
    )
    stored.rule_data = {**stored.rule_data, "source_quote": quote, "currency": "USD" if language == "en" else "EGP"}
    db.get(PolicyChunk, "chunk-rule-001").text = quote
    db.commit()
    before = (stored.approval_status, stored.approved_by, stored.approved_at, stored.verification_status)
    monkeypatch.setattr(main, "SessionLocal", lambda: Session(db.bind))
    result = main.list_policy_rules("policy-001")
    assert result["invalid_approved_rule_count"] == 1
    health = result["rules"][0]["current_validation"]
    assert health["status"] == "invalid"
    assert health["reason"] in {"policy_wording_unsupported", "policy_source_semantics_invalid"}
    with pytest.raises(PolicyRuleIntegrityError):
        load_approved_rules(db, "policy-001")
    db.refresh(stored)
    assert (stored.approval_status, stored.approved_by, stored.approved_at, stored.verification_status) == before


def test_rule_list_distinguishes_current_validity_from_pending_approval(db, monkeypatch):
    from app import main

    add_policy(db)
    add_rule(db)
    add_rule(db, rule_id="pending-rule", approval_status="pending")
    monkeypatch.setattr(main, "SessionLocal", lambda: Session(db.bind))
    result = main.list_policy_rules("policy-001")
    assert result["invalid_approved_rule_count"] == 0
    statuses = {rule["rule_id"]: rule["current_validation"]["status"] for rule in result["rules"]}
    assert statuses == {"rule-001": "valid", "pending-rule": "not_active"}
