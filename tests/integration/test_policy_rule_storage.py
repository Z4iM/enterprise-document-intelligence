
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.database.database import Base
from app.database.models import (
    PolicyDocument,
    StoredPolicyRule,
)
from app.validation.rule_schemas import PolicyRule


def test_policy_rule_storage_and_approval_constraint(tmp_path):
    database_path = tmp_path / "policy_rules.db"

    engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
    )

    Base.metadata.create_all(bind=engine)

    TestSession = sessionmaker(bind=engine)

    rule = PolicyRule(
        rule_id="MEAL-001",
        category="meal",
        field="total",
        operator=">",
        threshold=Decimal("100"),
        currency="USD",
        action="requires_approval",
        approval_role="manager",
        source_quote=(
            "Meal expenses above $100 require manager approval."
        ),
        source_chunk_id="chunk-meals",
    )

    try:
        with TestSession() as db:
            policy = PolicyDocument(
                id="policy-v1",
                original_filename="company_policy.txt",
                stored_file_path=str(tmp_path / "company_policy.txt"),
                file_hash="test-policy-hash",
                extracted_text=rule.source_quote,
            )

            stored_rule = StoredPolicyRule(
                id="stored-rule-1",
                policy_id=policy.id,
                rule_id=rule.rule_id,
                rule_data=rule.model_dump(mode="json"),
            )

            db.add(policy)
            db.add(stored_rule)
            db.commit()

            # Retrieve the persisted rule.
            saved = db.get(
                StoredPolicyRule,
                "stored-rule-1",
            )

            assert saved is not None
            assert saved.policy_id == "policy-v1"
            assert saved.rule_id == "MEAL-001"

            # Decimal is serialized safely as a string.
            assert saved.rule_data["threshold"] == "100"
            assert saved.rule_data["operator"] == ">"
            assert saved.rule_data["approval_role"] == "manager"

            # New rules must NOT be automatically approved.
            assert saved.verification_status == "pending"
            assert saved.approval_status == "pending"

            # Attempting to approve an unverified rule
            # must be rejected by the database.
            saved.approval_status = "approved"

            with pytest.raises(IntegrityError):
                db.commit()

            db.rollback()

            # The rejected update must not be persisted.
            db.refresh(saved)
            assert saved.approval_status == "pending"

    finally:
        engine.dispose()
