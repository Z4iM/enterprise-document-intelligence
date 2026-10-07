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
from app.database.models import Document, AuditEvent
from app.database.storage.file_storage import (
    generate_document_id,
    calculate_file_hash,
    save_original_file,
)
from sqlalchemy import select
from pathlib import Path
from fastapi.responses import FileResponse

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