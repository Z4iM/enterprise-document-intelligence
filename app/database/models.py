from datetime import datetime, UTC


from sqlalchemy import (
    String,
    Integer,
    Column,
    Float,
    Text,
    DateTime,
    JSON,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True
    )

    original_filename: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    stored_file_path: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    mime_type: Mapped[str | None] = mapped_column(
        String,
        nullable=True
    )

    file_size_bytes: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    file_hash: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    detected_type: Mapped[str | None] = mapped_column(
        String,
        nullable=True
    )

    text_extraction_method: Mapped[str | None] = mapped_column(
        String,
        nullable=True
    )

    extracted_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    document_type: Mapped[str | None] = mapped_column(
        String,
        nullable=True
    )

    classification_confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True
    )

    structured_extraction_method: Mapped[str | None] = mapped_column(
        String,
        nullable=True
    )

    structured_data: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True
    )

    review_status: Mapped[str] = mapped_column(
        String,
        default="processing"
    )

    processing_status: Mapped[str] = mapped_column(
        String,
        default="processing"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    document_id: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    event_type: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )
class HumanReview(Base):
    __tablename__ = "human_reviews"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    document_id: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    decision: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    reviewer: Mapped[str | None] = mapped_column(
        String,
        nullable=True
    )

    before_data: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True
    )

    corrections: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True
    )

    after_data: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )
class PolicyDocument(Base):
    __tablename__ = "policy_documents"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True
    )

    original_filename: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    stored_file_path: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    mime_type: Mapped[str | None] = mapped_column(
        String,
        nullable=True
    )

    file_hash: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    extracted_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )
class PolicyChunk(Base):
    __tablename__ = "policy_chunks"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True
    )

    policy_id: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    text: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
class PolicyValidation(Base):
    __tablename__ = "policy_validations"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    document_id = Column(
        String,
        nullable=False,
        index=True
    )

    status = Column(
        String,
        nullable=False
    )

    validation_result = Column(
        JSON,
        nullable=False
    )

    retrieved_chunks = Column(
        JSON,
        nullable=False
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

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

    # Serialized PolicyRule, including the original
    # source quotation and source chunk reference.
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
