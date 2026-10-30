"""Untrusted originals are parsed in bounded children; permissions are rechecked at execution."""

import hashlib
import uuid
from pathlib import Path

from sqlalchemy import select

from app.auth.security import (
    Principal,
    require_document,
    require_policy,
    require_reviewer,
)
from app.classification.classifier import classify_document, get_review_status
from app.database.models import AuditEvent, PolicyChunk, User
from app.database.storage import file_storage, policy_storage
from app.extraction.router import extract_structured_data
from app.ingestion.file_detector import detect_file_type
from app.ingestion.safety import MAX_FILE, extract_text_isolated
from app.rag.chunking import chunk_text
from app.validation.policy_extraction import (
    extract_whole_policy,
    generate_policy_output,
)


def process(db, job):
    user = db.get(User, job.actor_id)
    if not user or not user.active or user.organization_id != job.organization_id:
        raise ValueError("Job actor no longer authorized.")
    actor = Principal(user.id, user.organization_id, user.role)
    if job.kind == "document":
        resource = require_document(db, job.resource_id, actor)
        root = file_storage.UPLOAD_ROOT
    else:
        require_reviewer(actor)
        resource = require_policy(db, job.resource_id, actor)
        root = policy_storage.POLICY_ROOT
    path = Path(resource.stored_file_path).resolve()
    if not path.is_relative_to((root / resource.id).resolve()) or not path.is_file():
        raise ValueError("Original unavailable.")
    with path.open("rb") as original:
        raw = original.read(MAX_FILE + 1)
    if len(raw) > MAX_FILE or hashlib.sha256(raw).hexdigest() != resource.file_hash:
        raise ValueError("Original integrity failure.")
    kind = detect_file_type(resource.original_filename)
    text, method = extract_text_isolated(raw, kind)
    if job.kind == "policy_index":
        from app.rag.indexing import build_index
        build_index(db, resource, text)
        return
    if job.kind == "document":
        document_type, confidence = classify_document(text)
        data, structured_method, fallback = extract_structured_data(
            text=text, document_type=document_type
        )
        resource.extracted_text, resource.text_extraction_method = text, method
        resource.document_type, resource.classification_confidence = (
            document_type,
            confidence,
        )
        resource.structured_data, resource.structured_extraction_method = (
            data,
            structured_method,
        )
        resource.processing_status = "completed"
        resource.review_status = (
            "needs_review" if fallback else get_review_status(confidence)
        )
        if fallback:
            db.add(
                AuditEvent(
                    document_id=resource.id,
                    event_type="llm_fallback",
                    message="Model unavailable; review-gated fallback was used.",
                )
            )
        db.add(
            AuditEvent(
                document_id=resource.id,
                event_type="processing_completed",
                message="Document processing completed successfully.",
            )
        )
    else:
        existing = db.scalars(
            select(PolicyChunk)
            .where(PolicyChunk.policy_id == resource.id)
            .order_by(PolicyChunk.chunk_index)
        ).all()
        chunks = existing or [
            PolicyChunk(
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"edi:{resource.id}:{index}")),
                policy_id=resource.id,
                chunk_index=index,
                text=chunk,
            )
            for index, chunk in enumerate(chunk_text(text))
        ]
        # No flush/write transaction spans a remote model call, including on SQLite.
        output = generate_policy_output(chunks)
        resource.extracted_text = text
        if not existing:
            db.add_all(chunks)
        db.flush()
        extract_whole_policy(db, resource.id, managed=True, prepared_output=output)
