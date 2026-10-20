
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database.database import Base
from app.database.models import (
    PolicyChunk,
    PolicyDocument,
    StoredPolicyRule,
)
from app.validation.approved_rule_repository import (
    PolicyRuleIntegrityError,
    load_approved_rules,
)
from app.validation.rule_schemas import PolicyRule


@pytest.fixture
def db(tmp_path):
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'rules.db').as_posix()}"
    )

    Base.metadata.create_all(bind=engine)

    try:
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()


def create_test_rule(db):
    quote = (
        "Meal expenses above $100 require manager approval."
    )

    rule = PolicyRule(
        rule_id="MEAL-001",
        category="meal",
        field="total",
        operator=">",
        threshold=Decimal(100),
        action="requires_approval",
        approval_role="manager",
        source_quote=quote,
        source_chunk_id="chunk-meals",
    )

    db.add(
        PolicyDocument(
            id="policy-v1",
            original_filename="policy.txt",
            stored_file_path="test-policy.txt",
            file_hash="synthetic-hash",
            extracted_text=quote,
        )
    )

    db.add(
        PolicyChunk(
            id="chunk-meals",
            policy_id="policy-v1",
            chunk_index=0,
            text=quote,
        )
    )

    stored = StoredPolicyRule(
        id="stored-meal",
        policy_id="policy-v1",
        rule_id=rule.rule_id,
        rule_data=rule.model_dump(mode="json"),
    )

    db.add(stored)
    db.commit()

    return stored


def approve_test_rule(db, stored):
    stored.verification_status = "verified"
    stored.approval_status = "approved"
    stored.approved_by = "test-reviewer"
    stored.approved_at = datetime.now(UTC)
    db.commit()


def test_only_approved_rules_are_loaded(db):
    stored = create_test_rule(db)

    # Pending rules must never be evaluated.
    assert load_approved_rules(db, "policy-v1") == []

    # Simulate a verified and approved rule.
    approve_test_rule(db, stored)

    rules = load_approved_rules(db, "policy-v1")

    assert len(rules) == 1
    assert rules[0].rule_id == "MEAL-001"
    assert rules[0].threshold == Decimal(100)

    # Rules must be scoped to the requested policy.
    assert load_approved_rules(db, "another-policy") == []


def test_modified_source_quote_is_rejected(db):
    stored = create_test_rule(db)
    approve_test_rule(db, stored)

    # Simulate stored evidence being corrupted.
    modified_data = dict(stored.rule_data)
    modified_data["source_quote"] = (
        "A completely different policy statement."
    )

    stored.rule_data = modified_data
    db.commit()

    with pytest.raises(PolicyRuleIntegrityError):
        load_approved_rules(db, "policy-v1")
