from sqlalchemy.orm import Session

from app.database.models import Document
from app.observability.tracing import traced
from app.review.eligibility import document_eligibility


@traced("tool.inspect_document")
def inspect_document(
    document_id: str,
    allowed_document_ids: set[str],
    db: Session,
) -> dict:
    """
    Inspect a stored enterprise document.

    Read-only: never modifies the database.
    Access-scoped: only explicitly permitted document IDs.
    Review-aware: unverified extraction data is not exposed.
    """

    # 1. Validate authorization before accessing the database.
    if document_id not in allowed_document_ids:
        return {"status": "access_denied"}

    # 2. Retrieve the requested document.
    document = db.get(Document, document_id)

    if document is None:
        return {"status": "not_found"}

    # 3. Determine whether extraction data is trustworthy.
    decision, _ = document_eligibility(
        processing_status=document.processing_status,
        review_status=document.review_status,
        extraction_method=document.structured_extraction_method,
        structured_data=document.structured_data,
        document_type=document.document_type,
    )
    verified = decision == "ready"

    # 4. Return only the appropriate information.
    return {
        "status": "ready" if verified else "needs_review",
        "document_id": document.id,
        "document_type": document.document_type,
        "processing_status": document.processing_status,
        "review_status": document.review_status,
        "structured_data": (
            document.structured_data if verified else None
        ),
    }