from datetime import datetime

from sqlalchemy import (
    String,
    Integer,
    Column,
    Float,
    Text,
    DateTime,
    JSON,
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