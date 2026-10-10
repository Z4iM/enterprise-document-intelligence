
from sqlalchemy.orm import Session

from app.database.models import (
    Document,
    PolicyDocument,
    PolicyValidation,
)
from app.validation.approved_rule_repository import (
    load_approved_rules,
)
from app.validation.evaluation_service import (
    evaluate_verified_rules,
)


def validate_document_with_approved_rules(
    db: Session,
    document_id: str,
    policy_id: str,
) -> dict:
    """
    Evaluate one stored document against approved rules
    belonging to one selected policy.

    This evaluates the approved rule subset; it does not
    certify that every requirement in the policy is covered.
    """

    # 1. Load the business document.
    document = db.get(Document, document_id)

    if document is None:
        raise ValueError("Document not found.")

    if document.processing_status != "completed":
        raise ValueError("Document processing is incomplete.")

    if (
        not isinstance(document.structured_data, dict)
        or not document.structured_data
    ):
        raise ValueError("Structured document data is unavailable.")

    if document.structured_extraction_method == "regex_fallback":
        raise ValueError(
            "Fallback extraction requires review before validation."
        )

    # 2. Ensure the selected policy exists.
    policy = db.get(PolicyDocument, policy_id)

    if policy is None:
        raise ValueError("Policy not found.")

    # 3. Load ONLY verified and approved rules.
    approved_rules = load_approved_rules(
        db=db,
        policy_id=policy_id,
    )

    # 4. Evaluate document data against all eligible rules.
    evaluation = evaluate_verified_rules(
        document_data=document.structured_data,
        approved_rules=approved_rules,
    )

    # 5. Preserve the exact evidence for each evaluated rule.
    evidence = [
        {
            "policy_id": policy_id,
            "rule_id": rule.rule_id,
            "chunk_id": rule.source_chunk_id,
            "source_quote": rule.source_quote,
        }
        for rule in approved_rules
    ]

    validation_result = {
        "engine": "verified_rules_v1",
        "policy_id": policy_id,
        **evaluation,
        "evidence": evidence,
    }

    # 6. Save the validation result.
    record = PolicyValidation(
        document_id=document_id,
        status=evaluation["status"],
        validation_result=validation_result,
        retrieved_chunks=evidence,
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    return {
        "validation_id": record.id,
        "document_id": document_id,
        "policy_id": policy_id,
        "status": record.status,
        "validation": record.validation_result,
        "evidence": evidence,
    }
