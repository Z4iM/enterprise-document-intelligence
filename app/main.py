from fastapi import FastAPI, UploadFile, File, HTTPException
from app.ingestion.file_detector import detect_file_type
from app.ingestion.text_extractor import extract_text
from app.classification.classifier import (
    classify_document,
    get_review_status,
)
from app.extraction.router import extract_structured_data
from app.database.database import create_tables, SessionLocal
from app.database import models
from app.database.storage.file_storage import (
    generate_document_id,
    calculate_file_hash,
    save_original_file,
)
from sqlalchemy import select
from pathlib import Path
from fastapi.responses import FileResponse
from app.database.models import (
    Document,
    AuditEvent,
    HumanReview,
)
from app.review.schemas import ReviewRequest
import uuid
from app.database.models import (
    Document,
    AuditEvent,
    HumanReview,
    PolicyDocument,
    PolicyChunk,
    PolicyValidation,
)
from app.database.storage.policy_storage import (
    generate_policy_id,
    save_policy_file,
)
from app.rag.chunking import chunk_text


app = FastAPI(
    title="Enterprise Document Intelligence API",
    description="API for processing and analyzing enterprise documents.",
    version="0.1.0"
)
create_tables()

@app.get("/")
def root():
    return {
        "message": "Enterprise Document Intelligence API is running"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }
@app.get("/documents/{document_id}")
def get_document(document_id: str):

    with SessionLocal() as db:

        document = db.get(
            Document,
            document_id
        )

        if document is None:
            raise HTTPException(
                status_code=404,
                detail="Document not found"
            )

        return {
            "document_id": document.id,
            "filename": document.original_filename,
            "content_type": document.mime_type,

            "detected_type": document.detected_type,
            "extraction_method": document.text_extraction_method,

            "document_type": document.document_type,
            "classification_confidence": (
                document.classification_confidence
            ),

            "structured_extraction_method": (
                document.structured_extraction_method
            ),

            "review_status": document.review_status,
            "processing_status": document.processing_status,

            "structured_data": document.structured_data,

            "file_size_bytes": document.file_size_bytes,
            "file_hash": document.file_hash,

            "text_length": (
                len(document.extracted_text)
                if document.extracted_text
                else 0
            ),

            "text_preview": (
                document.extracted_text[:1000]
                if document.extracted_text
                else ""
            ),

            "created_at": document.created_at,
            "updated_at": document.updated_at
        }
@app.get("/documents")
def list_documents():

    with SessionLocal() as db:

        statement = (
            select(Document)
            .order_by(Document.created_at.desc())
        )

        documents = db.scalars(statement).all()

        return [
            {
                "document_id": document.id,
                "filename": document.original_filename,
                "document_type": document.document_type,
                "classification_confidence": (
                    document.classification_confidence
                ),
                "structured_extraction_method": (
                    document.structured_extraction_method
                ),
                "review_status": document.review_status,
                "processing_status": document.processing_status,
                "created_at": document.created_at
            }
            for document in documents
        ]
@app.get("/documents/{document_id}/audit")
def get_document_audit(document_id: str):

    with SessionLocal() as db:

        document = db.get(
            Document,
            document_id
        )

        if document is None:
            raise HTTPException(
                status_code=404,
                detail="Document not found"
            )

        statement = (
            select(AuditEvent)
            .where(
                AuditEvent.document_id == document_id
            )
            .order_by(AuditEvent.created_at.asc())
        )

        events = db.scalars(statement).all()

        return [
            {
                "id": event.id,
                "event_type": event.event_type,
                "message": event.message,
                "created_at": event.created_at
            }
            for event in events
        ]
@app.get("/documents/{document_id}/original")
def get_original_document(document_id: str):

    with SessionLocal() as db:

        document = db.get(
            Document,
            document_id
        )

        if document is None:
            raise HTTPException(
                status_code=404,
                detail="Document not found"
            )

        file_path = Path(document.stored_file_path)

        if not file_path.exists():
            raise HTTPException(
                status_code=404,
                detail="Original file not found"
            )

        return FileResponse(
            path=file_path,
            media_type=document.mime_type,
            filename=document.original_filename
        )
@app.get("/reviews/pending")
def get_pending_reviews():

    with SessionLocal() as db:

        statement = (
            select(Document)
            .where(
                Document.review_status == "needs_review"
            )
            .order_by(
                Document.created_at.asc()
            )
        )

        documents = db.scalars(statement).all()

        return [
            {
                "document_id": document.id,
                "filename": document.original_filename,
                "document_type": document.document_type,
                "classification_confidence": (
                    document.classification_confidence
                ),
                "structured_extraction_method": (
                    document.structured_extraction_method
                ),
                "structured_data": document.structured_data,
                "created_at": document.created_at
            }
            for document in documents
        ]
@app.get("/documents/{document_id}/reviews")
def get_document_reviews(document_id: str):

    with SessionLocal() as db:

        document = db.get(
            Document,
            document_id
        )

        if document is None:
            raise HTTPException(
                status_code=404,
                detail="Document not found"
            )

        statement = (
            select(HumanReview)
            .where(
                HumanReview.document_id == document_id
            )
            .order_by(
                HumanReview.created_at.asc()
            )
        )

        reviews = db.scalars(statement).all()

        return [
            {
                "id": review.id,
                "decision": review.decision,
                "reviewer": review.reviewer,
                "before_data": review.before_data,
                "corrections": review.corrections,
                "after_data": review.after_data,
                "notes": review.notes,
                "created_at": review.created_at
            }
            for review in reviews
        ]
@app.post("/documents/upload")
async def upload_document(file: UploadFile = File(...)):

    file_type = detect_file_type(file.filename)

    if file_type == "unsupported":
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type"
        )

    # Read uploaded file
    file_bytes = await file.read()

    # Calculate SHA-256 before saving
    file_hash = calculate_file_hash(file_bytes)

    with SessionLocal() as db:

        # Check whether this exact file already exists
        duplicate_statement = (
            select(Document)
            .where(Document.file_hash == file_hash)
        )

        existing_document = db.scalar(
            duplicate_statement
        )

        if existing_document is not None:

            db.add(
                AuditEvent(
                    document_id=existing_document.id,
                    event_type="duplicate_upload_attempt",
                    message=f"Duplicate upload attempted: {file.filename}"
                )
            )

            db.commit()

            raise HTTPException(
                status_code=409,
                detail={
                    "message": "This exact file has already been uploaded.",
                    "existing_document_id": existing_document.id
                }
            )

        # Only create a new document after duplicate check passes
        document_id = generate_document_id()

        # Save original file unchanged
        stored_file_path = save_original_file(
            file_bytes=file_bytes,
            original_filename=file.filename,
            document_id=document_id
        )

        # Create initial database record
        document = Document(
            id=document_id,
            original_filename=file.filename,
            stored_file_path=stored_file_path,
            mime_type=file.content_type,
            file_size_bytes=len(file_bytes),
            file_hash=file_hash,
            detected_type=file_type,
            processing_status="processing",
            review_status="processing"
        )

        db.add(document)

        db.add(
            AuditEvent(
                document_id=document_id,
                event_type="document_uploaded",
                message=f"Uploaded file: {file.filename}"
            )
        )

        db.commit()

        try:
            extracted_text, extraction_method = extract_text(
                file_bytes=file_bytes,
                file_type=file_type
            )

            (
                document_type,
                classification_confidence
            ) = classify_document(extracted_text)

            review_status = get_review_status(
                classification_confidence
            )

            (
                structured_data,
                structured_extraction_method,
                extraction_failed
            ) = extract_structured_data(
                text=extracted_text,
                document_type=document_type
            )

            if extraction_failed:
                review_status = "needs_review"

                db.add(
                    AuditEvent(
                        document_id=document_id,
                        event_type="llm_fallback",
                        message=(
                            "LLM extraction failed or was unavailable. "
                            "Rule-based fallback was used."
                        )
                    )
                )

            # Save processing results
            document.text_extraction_method = extraction_method
            document.extracted_text = extracted_text
            document.document_type = document_type
            document.classification_confidence = classification_confidence
            document.structured_extraction_method = (
                structured_extraction_method
            )
            document.structured_data = structured_data
            document.review_status = review_status
            document.processing_status = "completed"

            db.add(
                AuditEvent(
                    document_id=document_id,
                    event_type="processing_completed",
                    message="Document processing completed successfully."
                )
            )

            db.commit()

        except Exception as error:

            document.processing_status = "failed"
            document.review_status = "needs_review"

            db.add(
                AuditEvent(
                    document_id=document_id,
                    event_type="processing_failed",
                    message=str(error)
                )
            )

            db.commit()

            raise HTTPException(
                status_code=500,
                detail=f"Failed to process document: {str(error)}"
            )

    return {
        "document_id": document_id,

        "filename": file.filename,
        "content_type": file.content_type,

        "detected_type": file_type,
        "extraction_method": extraction_method,

        "document_type": document_type,
        "classification_confidence": classification_confidence,

        "structured_extraction_method": structured_extraction_method,

        "review_status": review_status,
        "processing_status": "completed",

        "structured_data": structured_data,

        "file_size_bytes": len(file_bytes),
        "file_hash": file_hash,

        "text_length": len(extracted_text),
        "text_preview": extracted_text[:1000]
    }
@app.post("/documents/{document_id}/review")
def review_document(
    document_id: str,
    review: ReviewRequest
):

    with SessionLocal() as db:

        document = db.get(
            Document,
            document_id
        )

        if document is None:
            raise HTTPException(
                status_code=404,
                detail="Document not found"
            )

        if document.processing_status != "completed":
            raise HTTPException(
                status_code=409,
                detail="Document processing is not completed"
            )

        before_data = (
            dict(document.structured_data)
            if document.structured_data
            else {}
        )

        final_data = dict(before_data)

        # -------------------------
        # APPROVED
        # -------------------------

        if review.decision == "approved":

            document.review_status = "approved"

        # -------------------------
        # CORRECTED
        # -------------------------

        elif review.decision == "corrected":

            if not review.corrections:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Corrections are required "
                        "when decision is 'corrected'"
                    )
                )

            for field, value in review.corrections.items():
                final_data[field] = value

            document.structured_data = final_data
            document.review_status = "corrected"

        # -------------------------
        # REJECTED
        # -------------------------

        elif review.decision == "rejected":

            document.review_status = "rejected"

        # -------------------------
        # SAVE REVIEW HISTORY
        # -------------------------

        human_review = HumanReview(
            document_id=document_id,
            decision=review.decision,
            reviewer=review.reviewer,
            before_data=before_data,
            corrections=review.corrections,
            after_data=final_data,
            notes=review.notes
        )

        db.add(human_review)

        db.add(
            AuditEvent(
                document_id=document_id,
                event_type="human_review",
                message=(
                    f"Document was {review.decision}"
                    + (
                        f" by {review.reviewer}"
                        if review.reviewer
                        else ""
                    )
                )
            )
        )

        db.commit()

        return {
            "document_id": document_id,
            "decision": review.decision,
            "review_status": document.review_status,
            "structured_data": document.structured_data,
            "corrections": review.corrections
        }
@app.post("/policies/upload")
async def upload_policy(file: UploadFile = File(...)):

    file_type = detect_file_type(file.filename)

    if file_type == "unsupported":
        raise HTTPException(
            status_code=400,
            detail="Unsupported policy file type"
        )

    file_bytes = await file.read()

    policy_hash = calculate_file_hash(file_bytes)

    with SessionLocal() as db:

        duplicate_statement = (
            select(PolicyDocument)
            .where(
                PolicyDocument.file_hash == policy_hash
            )
        )

        existing_policy = db.scalar(
            duplicate_statement
        )

        if existing_policy is not None:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "This policy already exists.",
                    "existing_policy_id": existing_policy.id
                }
            )

        policy_id = generate_policy_id()

        stored_file_path = save_policy_file(
            file_bytes=file_bytes,
            original_filename=file.filename,
            policy_id=policy_id
        )

        extracted_text, extraction_method = extract_text(
            file_bytes=file_bytes,
            file_type=file_type
        )

        policy = PolicyDocument(
            id=policy_id,
            original_filename=file.filename,
            stored_file_path=stored_file_path,
            mime_type=file.content_type,
            file_hash=policy_hash,
            extracted_text=extracted_text
        )

        db.add(policy)

        chunks = chunk_text(extracted_text)

        for index, chunk in enumerate(chunks):

            chunk_record = PolicyChunk(
                id=str(uuid.uuid4()),
                policy_id=policy_id,
                chunk_index=index,
                text=chunk
            )

            db.add(chunk_record)

        db.commit()

    return {
        "policy_id": policy_id,
        "filename": file.filename,
        "extraction_method": extraction_method,
        "text_length": len(extracted_text),
        "chunks_created": len(chunks)
    }
@app.post("/documents/{document_id}/validate-policy")
def validate_document_policy(document_id: str):

    with SessionLocal() as db:

        document = db.get(
            Document,
            document_id
        )

        if document is None:
            raise HTTPException(
                status_code=404,
                detail="Document not found"
            )

        if document.processing_status != "completed":
            raise HTTPException(
                status_code=409,
                detail="Document processing is not completed"
            )

        if (
            not document.structured_data
            or document.structured_extraction_method
            == "regex_fallback"
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    "Reliable structured data is unavailable. "
                    "Human review is required before policy validation."
                )
            )
        from app.rag.validation_service import run_policy_validation
        try:
            result = run_policy_validation(
                
                db=db,
                document_id=document.id,
                document_type=document.document_type,
                structured_data=document.structured_data,
                document_text=document.extracted_text or ""
            )

        except Exception as error:
            raise HTTPException(
                status_code=503,
                detail="Policy validation service unavailable"
            ) from error

        return result