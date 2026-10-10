
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import (
    PolicyDocument,
    PolicyChunk,
    StoredPolicyRule,
)
from app.llm.base import LLMProvider
from app.validation.rule_schemas import PolicyRule
from app.validation.two_stage_extractor import extract_verified_rules


def extract_and_store_candidates(
    db: Session,
    policy_id: str,
    chunk_index: int,
    provider: LLMProvider,
) -> dict:
    """Extract candidate rules from a stored policy chunk."""

    policy = db.get(PolicyDocument, policy_id)

    if policy is None:
        raise LookupError("Policy not found.")

    chunk = db.scalar(
        select(PolicyChunk).where(
            PolicyChunk.policy_id == policy_id,
            PolicyChunk.chunk_index == chunk_index,
        )
    )

    if chunk is None:
        raise LookupError("Policy chunk not found.")

    # Run existing Qwen extraction + source verification.
    result = extract_verified_rules(
        policy_text=chunk.text,
        chunk_id=chunk.id,
        provider=provider,
    )

    saved_rules = []
    existing_rules = []
    rejected_rules = list(result["rejected_rules"])

    for rule_number, rule_data in enumerate(
        result["verified_rules"],
        start=1,
    ):
        rule_data = dict(rule_data)

        # Generate deterministic identifiers in Python.
        rule_data["rule_id"] = (
            f"CHUNK-{chunk_index:03d}-RULE-{rule_number:03d}"
        )

        rule = PolicyRule.model_validate(rule_data)

        # Recheck provenance before persistence.
        if (
            rule.source_chunk_id != chunk.id
            or not rule.source_quote
            or rule.source_quote not in chunk.text
        ):
            rejected_rules.append({
                "rule_id": rule.rule_id,
                "reason": "Invalid or missing source evidence.",
            })
            continue

        existing = db.scalar(
            select(StoredPolicyRule).where(
                StoredPolicyRule.policy_id == policy_id,
                StoredPolicyRule.rule_id == rule.rule_id,
            )
        )

        if existing is not None:
            if existing.rule_data != rule.model_dump(mode="json"):
                rejected_rules.append({
                    "rule_id": rule.rule_id,
                    "reason": (
                        "Rule ID already exists with different data. "
                        "Manual resolution required."
                    ),
                })
            else:
                existing_rules.append(rule.rule_id)

            # Never overwrite an existing approved rule.
            continue

        stored = StoredPolicyRule(
            id=str(uuid.uuid4()),
            policy_id=policy_id,
            rule_id=rule.rule_id,
            rule_data=rule.model_dump(mode="json"),
            verification_status="verified",
            approval_status="pending",
        )

        db.add(stored)

        saved_rules.append({
            "id": stored.id,
            "rule_id": rule.rule_id,
            "rule_data": stored.rule_data,
            "verification_status": "verified",
            "approval_status": "pending",
        })

    if saved_rules:
        db.commit()

    return {
        "policy_id": policy_id,
        "chunk_id": chunk.id,
        "chunk_index": chunk_index,
        "extraction_status": result["status"],
        "saved_count": len(saved_rules),
        "saved_rules": saved_rules,
        "existing_rules": existing_rules,
        "rejected_rules": rejected_rules,
    }
