
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


def utc_now_naive() -> datetime:
    """
    Return a naive UTC datetime for compatibility
    with existing SQLite timestamp columns.
    """
    return datetime.now(UTC).replace(tzinfo=None)


# =========================================================
# DOCUMENTS
# =========================================================

class Document(Base):
    __tablename__ = "documents"

    organization_id: Mapped[str] = mapped_column(String, default="legacy-unassigned", nullable=False, index=True)
    owner_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
    )

    original_filename: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    stored_file_path: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    mime_type: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    file_size_bytes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    file_hash: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    detected_type: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    text_extraction_method: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    extracted_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    document_type: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    classification_confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    structured_extraction_method: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    structured_data: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    review_status: Mapped[str] = mapped_column(
        String,
        default="processing",
    )

    processing_status: Mapped[str] = mapped_column(
        String,
        default="processing",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now_naive,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now_naive,
        onupdate=utc_now_naive,
    )


# =========================================================
# DOCUMENT AUDIT EVENTS
# =========================================================

class AuditEvent(Base):
    __tablename__ = "audit_events"

    actor_id: Mapped[str | None] = mapped_column(String, nullable=True)

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    document_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    event_type: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now_naive,
    )


# =========================================================
# HUMAN DOCUMENT REVIEWS
# =========================================================

class HumanReview(Base):
    __tablename__ = "human_reviews"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    document_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    decision: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    reviewer: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    before_data: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    corrections: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    after_data: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now_naive,
    )


# =========================================================
# POLICY DOCUMENTS
# =========================================================

class PolicyDocument(Base):
    __tablename__ = "policy_documents"

    rule_extraction_status: Mapped[str] = mapped_column(String, default="not_started", nullable=False)
    rule_extraction_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    organization_id: Mapped[str] = mapped_column(String, default="legacy-unassigned", nullable=False, index=True)
    owner_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
    )

    original_filename: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    stored_file_path: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    mime_type: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    file_hash: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    extracted_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now_naive,
    )


# =========================================================
# POLICY CHUNKS
# =========================================================

class PolicyChunk(Base):
    __tablename__ = "policy_chunks"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
    )

    policy_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )


# =========================================================
# POLICY VALIDATION RESULTS
# =========================================================

class PolicyValidation(Base):
    __tablename__ = "policy_validations"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    document_id = Column(
        String,
        nullable=False,
        index=True,
    )

    status = Column(
        String,
        nullable=False,
    )

    validation_result = Column(
        JSON,
        nullable=False,
    )

    retrieved_chunks = Column(
        JSON,
        nullable=False,
    )

    created_at = Column(
        DateTime,
        default=utc_now_naive,
    )


# =========================================================
# STORED POLICY RULES
# =========================================================

class StoredPolicyRule(Base):
    __tablename__ = "stored_policy_rules"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
    )

    policy_id: Mapped[str] = mapped_column(
        ForeignKey("policy_documents.id"),
        nullable=False,
        index=True,
    )

    rule_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    # Serialized verified rule and its source evidence.
    rule_data: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
    )

    verification_status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="pending",
    )

    approval_status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="pending",
    )

    approved_by: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "policy_id",
            "rule_id",
            name="uq_policy_rule_per_policy",
        ),
        CheckConstraint(
            "verification_status IN "
            "('pending', 'verified', 'rejected')",
            name="ck_policy_rule_verification_status",
        ),
        CheckConstraint(
            "approval_status IN "
            "('pending', 'approved', 'rejected')",
            name="ck_policy_rule_approval_status",
        ),
        CheckConstraint(
            "approval_status != 'approved' "
            "OR verification_status = 'verified'",
            name="ck_approval_requires_verification",
        ),
    )


# =========================================================
# POLICY RULE HUMAN REVIEW HISTORY
# =========================================================

class PolicyRuleReview(Base):
    __tablename__ = "policy_rule_reviews"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    stored_rule_id: Mapped[str] = mapped_column(
        ForeignKey("stored_policy_rules.id"),
        nullable=False,
        index=True,
    )

    decision: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    reviewer: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


class User(Base):
    __tablename__ = "users"
    display_name: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    organization_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    __table_args__ = (CheckConstraint("role IN ('employee','reviewer','admin')", name="ck_user_role"),)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    token_hash: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    csrf_hash: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class SecurityEvent(Base):
    __tablename__ = "security_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[str | None] = mapped_column(String, nullable=True)
    organization_id: Mapped[str | None] = mapped_column(String, nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String, nullable=True)
    action: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)


class RequestLimit(Base):
    __tablename__ = "request_limits"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    window: Mapped[int] = mapped_column(Integer, nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False)


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    organization_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    owner_id: Mapped[str] = mapped_column(String, nullable=False)
    document_id: Mapped[str] = mapped_column(String, nullable=False)
    policy_id: Mapped[str] = mapped_column(String, nullable=False)


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    resource_id: Mapped[str] = mapped_column(String, nullable=False)
    organization_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(String, nullable=False)
    state: Mapped[str] = mapped_column(String, nullable=False, default="queued", index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    available_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now_naive)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    lease_token: Mapped[str | None] = mapped_column(String, nullable=True)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now_naive)
    __table_args__ = (
        UniqueConstraint("kind", "resource_id", name="uq_job_resource"),
        CheckConstraint("kind IN ('document','policy','policy_index')", name="ck_job_kind"),
        CheckConstraint("state IN ('queued','running','retry_wait','completed','failed')", name="ck_job_state"),
    )


class PolicySearchIndex(Base):
    __tablename__ = "policy_search_indexes"
    policy_id: Mapped[str] = mapped_column(ForeignKey("policy_documents.id"), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    state: Mapped[str] = mapped_column(String, default="queued", nullable=False)
    source_digest: Mapped[str | None] = mapped_column(String, nullable=True)
    model_id: Mapped[str | None] = mapped_column(String, nullable=True)
    passage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
    __table_args__ = (CheckConstraint("state IN ('queued','ready','failed','removed')", name="ck_search_state"),)


class SearchPassage(Base):
    __tablename__ = "search_passages"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    policy_id: Mapped[str] = mapped_column(ForeignKey("policy_documents.id"), nullable=False, index=True)
    chunk_id: Mapped[str] = mapped_column(ForeignKey("policy_chunks.id"), nullable=False, index=True)
    start: Mapped[int] = mapped_column(Integer, nullable=False)
    end: Mapped[int] = mapped_column(Integer, nullable=False)
    source_hash: Mapped[str] = mapped_column(String, nullable=False)
    language: Mapped[str] = mapped_column(String, nullable=False)
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)
    model_id: Mapped[str | None] = mapped_column(String, nullable=True)
    __table_args__ = (CheckConstraint('"start" >= 0 AND "end" > "start"', name="ck_passage_offsets"),)
