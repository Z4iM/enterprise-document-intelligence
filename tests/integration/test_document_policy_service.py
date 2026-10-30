
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.database.database import Base
from app.database.models import (
    Document,
    PolicyChunk,
    PolicyDocument,
    PolicyValidation,
    StoredPolicyRule,
)
from app.validation.document_policy_service import (
    validate_document_with_approved_rules,
)
from app.validation.rule_schemas import PolicyRule


def test_document_policy_validation_is_persisted(tmp_path):
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'validation.db').as_posix()}"
    )

    Base.metadata.create_all(bind=engine)

    try:
        with Session(engine) as db:

            # Create a synthetic processed receipt.
            db.add(
                Document(
                    id="receipt-001",
                    original_filename="meal_receipt.pdf",
                    stored_file_path="test/meal_receipt.pdf",
                    mime_type="application/pdf",
                    file_size_bytes=100,
                    file_hash="synthetic-receipt-hash",
                    detected_type="pdf",
                    document_type="receipt",
                    processing_status="completed",
                    review_status="approved",
                    structured_extraction_method="llm",
                    structured_data={
                        "expense_category": "meal",
                        "total": "$175.00",
                    },
                )
            )

            # Create a synthetic company policy.
            db.add(
                PolicyDocument(
                    id="company-policy-v1",
                    original_filename="policy.docx",
                    stored_file_path="test/policy.docx",
                    file_hash="synthetic-policy-hash",
                )
            )

            rules = [
                PolicyRule(
                    rule_id="MEAL-001",
                    category="meal",
                    field="total",
                    operator=">",
                    threshold=Decimal(100),
                    action="requires_approval",
                    approval_role="manager",
                    source_quote=(
                        "Meal expenses above $100 require "
                        "manager approval."
                    ),
                    source_chunk_id="chunk-meal",
                ),
                PolicyRule(
                    rule_id="RECEIPT-001",
                    category="all_expenses",
                    field="total",
                    operator=">=",
                    threshold=Decimal(25),
                    action="requires_documentation",
                    source_quote=(
                        "Expenses of $25 or more require a receipt."
                    ),
                    source_chunk_id="chunk-receipt",
                ),
            ]

            for index, rule in enumerate(rules):
                db.add(
                    PolicyChunk(
                        id=rule.source_chunk_id,
                        policy_id="company-policy-v1",
                        chunk_index=index,
                        text=rule.source_quote,
                    )
                )

                db.add(
                    StoredPolicyRule(
                        id=f"stored-{rule.rule_id}",
                        policy_id="company-policy-v1",
                        rule_id=rule.rule_id,
                        rule_data=rule.model_dump(mode="json"),
                        verification_status="verified",
                        approval_status="approved",
                        approved_by="test-reviewer",
                        approved_at=datetime.now(UTC),
                    )
                )

            db.commit()

            # Run the actual integrated validation service.
            result = validate_document_with_approved_rules(
                db=db,
                document_id="receipt-001",
                policy_id="company-policy-v1",
            )

            assert result["status"] == "requires_approval"

            validation = result["validation"]

            assert validation["rules_evaluated"] == 2
            assert validation["applicable_rules"] == 2
            assert len(validation["required_actions"]) == 2

            actions = {
                action["action"]
                for action in validation["required_actions"]
            }

            assert actions == {
                "requires_approval",
                "requires_documentation",
            }

            # Confirm that a validation record was saved.
            saved = db.scalar(
                select(PolicyValidation).where(
                    PolicyValidation.document_id == "receipt-001"
                )
            )

            assert saved is not None
            assert saved.status == "requires_approval"
            assert saved.validation_result["policy_id"] == (
                "company-policy-v1"
            )

            # Both supporting policy quotes are preserved.
            assert len(saved.retrieved_chunks) == 2

    finally:
        engine.dispose()
