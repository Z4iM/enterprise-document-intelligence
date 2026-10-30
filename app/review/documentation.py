"""Receipt requirement != missing receipt. Only scoped human evidence review resolves it."""

import hashlib
import json
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.auth.security import (
    authorize_request,
    require_document,
    require_policy,
    require_reviewer,
    session_factory,
    throttle,
)
from app.database.models import (
    AuditEvent,
    Document,
    DocumentationReview,
    User,
    utc_now_naive,
)
from app.language.amounts import semantic_text
from app.review.eligibility import document_eligibility
from app.validation.approved_rule_repository import (
    PolicyRuleIntegrityError,
    load_approved_rules,
)
from app.validation.evaluation_service import evaluate_verified_rules

router = APIRouter(dependencies=[Depends(authorize_request)])


def eligible(document):
    return (
        document_eligibility(
            processing_status=document.processing_status,
            review_status=document.review_status,
            extraction_method=document.structured_extraction_method,
            structured_data=document.structured_data,
            document_type=document.document_type,
        )[0]
        == "ready"
    )


def requirement_kind(quote):
    text = semantic_text(quote)
    kinds = []
    if re.search(r"\breceipts?\b|ايصال|إيصال|ايصالات|إيصالات", text):
        kinds.append("receipt")
    if re.search(r"\binvoices?\b|فاتورة|فواتير", text):
        kinds.append("invoice")
    return kinds[0] if len(kinds) == 1 else "unspecified"


def evidence_digest(rule, target, documents):
    def facts(doc):
        return {
            "id": doc.id,
            "hash": doc.file_hash,
            "type": doc.document_type,
            "fields": doc.structured_data,
            "review": doc.review_status,
            "method": doc.structured_extraction_method,
        }

    payload = {
        "rule": rule.model_dump(mode="json"),
        "target": facts(target),
        "evidence": [facts(doc) for doc in sorted(documents, key=lambda item: item.id)],
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def checked_evidence(db, actor, target, identifiers):
    documents = [
        require_document(db, identifier, actor)
        for identifier in sorted(set(identifiers))
    ]
    if any(
        doc.owner_id != target.owner_id or doc.organization_id != target.organization_id
        for doc in documents
    ):
        raise HTTPException(404, "Supporting document not available for this owner.")
    if not documents or any(not eligible(doc) for doc in documents):
        raise HTTPException(
            409, "Every supporting document must have validated human-reviewed fields."
        )
    return documents


def documentation_checklist(db, actor, document_id, policy_id):
    target = require_document(db, document_id, actor)
    require_policy(db, policy_id, actor)
    if not eligible(target):
        return {"status": "needs_document_review", "requirements": []}
    try:
        rules = load_approved_rules(db, policy_id)
    except PolicyRuleIntegrityError:
        return {"status": "needs_policy_review", "requirements": []}
    if not rules:
        return {"status": "needs_policy_review", "requirements": []}
    evaluation = evaluate_verified_rules(target.structured_data, rules)
    if evaluation["status"] == "needs_review":
        return {
            "status": "needs_document_review"
            if evaluation.get("applicable_rules")
            else "needs_policy_review",
            "requirements": [],
        }
    triggered = {
        item["rule_id"]
        for item in evaluation["required_actions"]
        if item["action"] == "requires_documentation"
    }
    items = []
    for rule in rules:
        if rule.rule_id not in triggered:
            continue
        kind = requirement_kind(rule.source_quote)
        review = db.scalar(
            select(DocumentationReview)
            .where(
                DocumentationReview.document_id == target.id,
                DocumentationReview.policy_id == policy_id,
                DocumentationReview.rule_id == rule.rule_id,
            )
            .order_by(
                DocumentationReview.created_at.desc(), DocumentationReview.id.desc()
            )
            .limit(1)
        )
        state, reviewed_ids = (
            ("needs_clarification" if kind == "unspecified" else "requires_review"),
            [],
        )
        if review and kind != "unspecified":
            reviewer = db.get(User, review.reviewer_id)
            try:
                documents = checked_evidence(db, actor, target, review.evidence_ids)
                valid = (
                    reviewer
                    and reviewer.active
                    and reviewer.organization_id == actor.organization_id
                    and reviewer.role in {"reviewer", "admin"}
                    and any(doc.document_type == kind for doc in documents)
                    and review.source_digest == evidence_digest(rule, target, documents)
                )
            except HTTPException:
                valid = False
            state = "reviewed_satisfied" if valid else "stale_review"
            reviewed_ids = review.evidence_ids if valid else []
        items.append(
            {
                "rule_id": rule.rule_id,
                "kind": kind,
                "status": state,
                "source_quote": rule.source_quote,
                "source_chunk_id": rule.source_chunk_id,
                "candidate_document_ids": [target.id]
                if target.document_type == kind
                else [],
                "reviewed_document_ids": reviewed_ids,
                "explanation": "Policy does not specify acceptable documentation; seek clarification."
                if kind == "unspecified"
                else "An uploaded document may satisfy this requirement; a reviewer must check its contents. This is not expense approval.",
            }
        )
    return {
        "status": "reviewed"
        if items and all(item["status"] == "reviewed_satisfied" for item in items)
        else "requires_review"
        if items
        else "not_required_by_triggered_rules",
        "requirements": items,
        "coverage": "approved_rules_only_not_expense_approval",
    }


class EvidenceReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    policy_id: str = Field(min_length=1, max_length=128)
    rule_id: str = Field(min_length=1, max_length=128)
    evidence_ids: list[str] = Field(min_length=1, max_length=5)
    note: str = Field(min_length=10, max_length=500)

    @field_validator("evidence_ids")
    @classmethod
    def bounded_identifiers(cls, values):
        if any(not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value) for value in values):
            raise ValueError("Invalid evidence identifier.")
        return values

    @field_validator("note")
    @classmethod
    def meaningful_note(cls, value):
        if len(value.strip()) < 10:
            raise ValueError("Record what was verified.")
        return value.strip()


@router.get("/documents/{document_id}/documentation/{policy_id}")
def get_documentation(document_id: str, policy_id: str, request: Request):
    with session_factory(request)() as db:
        return documentation_checklist(db, request.state.actor, document_id, policy_id)


@router.get("/documents/{document_id}/documentation-candidates")
def get_candidates(document_id: str, request: Request):
    with session_factory(request)() as db:
        target = require_document(db, document_id, request.state.actor)
        rows = db.scalars(
            select(Document)
            .where(
                Document.organization_id == target.organization_id,
                Document.owner_id == target.owner_id,
                Document.processing_status == "completed",
                Document.review_status.in_(["approved", "corrected"]),
            )
            .order_by((Document.id == target.id).desc(), Document.created_at.desc())
            .limit(51)
        ).all()
        return {
            "candidates": [
                {
                    "document_id": doc.id,
                    "filename": doc.original_filename,
                    "document_type": doc.document_type,
                }
                for doc in rows[:50]
                if eligible(doc)
            ],
            "truncated": len(rows) > 50,
        }


@router.post("/documents/{document_id}/documentation")
def review_documentation(document_id: str, body: EvidenceReview, request: Request):
    actor = request.state.actor
    require_reviewer(actor)
    with session_factory(request)() as db:
        throttle(db, "documentation-review:" + actor.id, 20)
        checklist = documentation_checklist(db, actor, document_id, body.policy_id)
        item = next(
            (
                item
                for item in checklist["requirements"]
                if item["rule_id"] == body.rule_id
            ),
            None,
        )
        if item is None or item["kind"] == "unspecified":
            raise HTTPException(
                409,
                "No specific triggered documentation requirement is available for review.",
            )
        target = require_document(db, document_id, actor)
        evidence = checked_evidence(db, actor, target, body.evidence_ids)
        if not any(doc.document_type == item["kind"] for doc in evidence):
            raise HTTPException(
                422, "Evidence type does not match the explicit policy requirement."
            )
        try:
            rule = next(
                rule
                for rule in load_approved_rules(db, body.policy_id)
                if rule.rule_id == body.rule_id
            )
        except (StopIteration, PolicyRuleIntegrityError):
            raise HTTPException(409, "Policy changed; refresh its requirements.") from None
        review = db.scalar(
            select(DocumentationReview)
            .where(
                DocumentationReview.document_id == target.id,
                DocumentationReview.policy_id == body.policy_id,
                DocumentationReview.rule_id == body.rule_id,
            )
            .order_by(
                DocumentationReview.created_at.desc(), DocumentationReview.id.desc()
            )
            .limit(1)
        )
        digest = evidence_digest(rule, target, evidence)
        identifiers = sorted({doc.id for doc in evidence})
        if (
            review is not None
            and review.reviewer_id == actor.id
            and review.source_digest == digest
            and review.evidence_ids == identifiers
            and review.note == body.note
        ):
            return documentation_checklist(db, actor, target.id, body.policy_id)
        review = DocumentationReview(
            id=str(uuid.uuid4()),
            document_id=target.id,
            policy_id=body.policy_id,
            rule_id=body.rule_id,
        )
        db.add(review)
        review.reviewer_id, review.evidence_ids = (
            actor.id,
            sorted({doc.id for doc in evidence}),
        )
        review.source_digest, review.note, review.created_at = (
            evidence_digest(rule, target, evidence),
            body.note.strip(),
            utc_now_naive(),
        )
        db.add(
            AuditEvent(
                document_id=target.id,
                actor_id=actor.id,
                event_type="documentation_reviewed",
                message="Supporting evidence explicitly reviewed; no expense approval granted.",
            )
        )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                409, "Concurrent evidence review; refresh and retry."
            ) from None
        db.expire_all()
        return documentation_checklist(db, actor, target.id, body.policy_id)
