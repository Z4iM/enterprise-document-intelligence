"""Shared review boundary for API, workflow and investigation tools."""

from typing import Literal

from pydantic import ValidationError

from app.llm.schemas import SCHEMA_MAP


def validate_review_data(document_type: str | None, data: object) -> dict:
    """Validate human-reviewed fields without rewriting extraction provenance."""
    schema = SCHEMA_MAP.get(document_type)
    if schema is None or not isinstance(data, dict) or not data:
        raise ValueError("Supported, non-empty structured data is required.")
    if set(data) - set(schema.model_fields):
        raise ValueError("Structured data contains unsupported fields.")
    try:
        schema.model_validate(data, strict=True)
    except ValidationError as error:
        raise ValueError(
            "Structured data does not match the document schema."
        ) from error
    if not any(value not in (None, "", []) for value in data.values()):
        raise ValueError("Structured data must contain a reviewed value.")
    return dict(data)


def document_eligibility(
    *,
    processing_status: str | None,
    review_status: str | None,
    extraction_method: str | None,
    structured_data: object,
    document_type: str | None = None,
) -> tuple[Literal["ready", "needs_review", "blocked"], str]:
    if processing_status != "completed":
        return "blocked", "Document processing is incomplete or failed."
    if review_status == "rejected":
        return "blocked", "Document was rejected by a reviewer."
    if review_status not in {"approved", "corrected"}:
        return "needs_review", "Human document review is required."
    if not isinstance(structured_data, dict) or not structured_data:
        return "needs_review", "Structured document data is unavailable."
    try:
        validate_review_data(document_type, structured_data)
    except ValueError as error:
        return "needs_review", str(error)
    if extraction_method == "llm":
        return "ready", "Document data was explicitly reviewed."
    if extraction_method == "regex_fallback" and review_status == "corrected":
        return "ready", "Fallback data was corrected and validated."
    return "needs_review", "Document requires extraction verification and correction."
