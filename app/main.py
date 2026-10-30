import logging
import os
import threading
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal

from fastapi import (
    Body,
    Depends,
    FastAPI,
    File,
    Header,
    HTTPException,
    Request,
    Response,
    UploadFile,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from app.agents.api import router as agent_router
from app.auth.api import router as auth_router
from app.auth.envelope import SecurityEnvelope
from app.auth.profiles import user_label
from app.auth.security import authorize_request, document_filter, require_policy
from app.classification.classifier import (
    classify_document,
    get_review_status,
)
from app.database.database import SessionLocal
from app.database.models import (
    AuditEvent,
    Document,
    HumanReview,
    PolicyChunk,
    PolicyDocument,
)
from app.database.storage import file_storage, policy_storage
from app.database.storage.file_storage import (
    calculate_file_hash,
    generate_document_id,
    save_original_file,
)
from app.database.storage.policy_storage import (
    generate_policy_id,
    save_policy_file,
)
from app.extraction.router import extract_structured_data
from app.ingestion.safety import extract_text_isolated as extract_text
from app.ingestion.safety import read_upload
from app.jobs.api import router as jobs_router
from app.rag.api import router as retrieval_router
from app.rag.chunking import chunk_text
from app.review.documentation import router as documentation_router
from app.review.eligibility import validate_review_data
from app.review.schemas import ReviewRequest
from app.specialists.api import router as specialists_router
from app.workflows.api import router as workflow_router


def processing_mode():
    value = os.getenv("EDI_PROCESSING_MODE", "embedded")
    if value not in {"embedded", "external", "inline"}:
        raise RuntimeError("Invalid processing mode.")
    return value


@asynccontextmanager
async def lifespan(application):
    stop = threading.Event()
    thread = None
    if processing_mode() == "embedded":
        from app.jobs.worker import serve
        thread = threading.Thread(target=serve, args=(stop, lambda: SessionLocal()), daemon=True)
        thread.start()
    try:
        yield
    finally:
        stop.set()
        if thread:
            await run_in_threadpool(thread.join, 5)


app = FastAPI(
    lifespan=lifespan,
    dependencies=[Depends(authorize_request)],
    title="Enterprise Document Intelligence API",
    description="API for processing and analyzing enterprise documents.",
    version="0.1.0"
)
app.include_router(agent_router)
app.include_router(workflow_router)
app.include_router(auth_router)
app.include_router(jobs_router)
app.include_router(retrieval_router)
app.include_router(documentation_router)
app.include_router(specialists_router)
app.state.resource_session_factory = lambda: SessionLocal()
app.add_middleware(SecurityEnvelope)


@app.exception_handler(RequestValidationError)
async def invalid_request(request, error):
    # FastAPI's default error includes submitted values, including passwords.
    return JSONResponse({"detail": "Invalid request fields."}, status_code=422)


@app.exception_handler(OperationalError)
async def unavailable_database(request, error):
    return JSONResponse({"detail": "Database unavailable or migrations required."}, status_code=503)


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


@app.get("/ready")
def readiness():
    try:
        with SessionLocal() as db:
            if db.scalar(text("SELECT version_num FROM alembic_version")) != "20261030_specialists":
                raise HTTPException(503, "Database migrations required.")
    except SQLAlchemyError as error:
        raise HTTPException(503, "Database unavailable or migrations required.") from error
    return {"status": "ready"}


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
def list_documents(request: Request):

    with SessionLocal() as db:

        statement = (
            select(Document)
            .where(*document_filter(request.state.actor))
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

        def readable_event(event):
            message = event.message
            actor_id = event.actor_id
            # Legacy human-review messages embedded the actor ID in plain text.
            if event.event_type == "human_review" and message and " by " in message:
                message, legacy_actor = message.rsplit(" by ", 1)
                actor_id = actor_id or legacy_actor
            name = user_label(db, actor_id, document.organization_id) if actor_id else None
            return {"id": event.id, "event_type": event.event_type,
                    "message": f"{message} by {name}" if name else message,
                    "actor_name": name, "created_at": event.created_at}

        return [readable_event(event) for event in events]
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

        if not file_path.resolve().is_relative_to((file_storage.UPLOAD_ROOT / document_id).resolve()) or not file_path.is_file():
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
def get_pending_reviews(request: Request):

    with SessionLocal() as db:

        statement = (
            select(Document)
            .where(
                Document.review_status.in_({"needs_review", "auto_accepted"}),
                Document.processing_status == "completed",
                *document_filter(request.state.actor)
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
                "reviewer_name": user_label(db, review.reviewer, document.organization_id),
                "before_data": review.before_data,
                "corrections": review.corrections,
                "after_data": review.after_data,
                "notes": review.notes,
                "created_at": review.created_at
            }
            for review in reviews
        ]
@app.post("/documents/upload")
async def upload_document(
    request: Request,
    response: Response,
    file: Annotated[UploadFile, File()],
):

    file_bytes, file_type, content_type = await read_upload(file)

    # Calculate SHA-256 before saving
    file_hash = calculate_file_hash(file_bytes)

    with SessionLocal() as db:

        # Check whether this exact file already exists
        duplicate_statement = (
            select(Document)
            .where(Document.file_hash == file_hash, *document_filter(request.state.actor))
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
            organization_id=request.state.actor.organization_id,
            owner_id=request.state.actor.id,
            original_filename=file.filename,
            stored_file_path=stored_file_path,
            mime_type=content_type,
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

        if processing_mode() != "inline":
            from app.jobs.queue import enqueue
            job = enqueue(db, "document", document_id, request.state.actor)
            document.processing_status = "queued"
            db.commit()
            response.status_code = 202
            return {**get_document(document_id), "job_id": job.id}

        db.commit()
        try:
            extracted_text, extraction_method = await run_in_threadpool(extract_text,
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
            ) = await run_in_threadpool(extract_structured_data,
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
            # Log the original exception and its traceback.
            logging.getLogger(__name__).error(
                "Document processing failed: document_id=%s",
                document_id,
            )

            # Reset any failed or uncommitted transaction.
            db.rollback()

            # Best-effort recording of the failed processing attempt.
            try:
                failed_document = db.get(
                    Document,
                    document_id,
                )

                if failed_document is not None:
                    failed_document.processing_status = "failed"
                    failed_document.review_status = "needs_review"

                    db.add(
                        AuditEvent(
                            document_id=document_id,
                            event_type="processing_failed",
                            message=(
                                "Document processing failed. "
                                "See server logs for details."
                            ),
                        )
                    )

                    db.commit()

            except SQLAlchemyError:
                # Failure logging must not hide the original error.
                db.rollback()

                logging.getLogger(__name__).error(
                    "Could not persist processing failure: "
                    "document_id=%s",
                    document_id,
                )

            # Never expose the original exception to API clients.
            raise HTTPException(
                status_code=500,
                detail="Document processing failed.",
            ) from error


    return {
        "document_id": document_id,

        "filename": file.filename,
        "content_type": content_type,

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
    review: ReviewRequest,
    request: Request,
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
            if isinstance(document.structured_data, dict)
            else {}
        )

        final_data = dict(before_data)

        if review.decision in {"approved", "corrected"}:
            if (
                review.decision == "approved"
                and document.structured_extraction_method != "llm"
            ):
                raise HTTPException(
                    status_code=409,
                    detail="Fallback extraction requires an explicit correction before evaluation.",
                )
            candidate = dict(final_data)
            if review.decision == "corrected" and review.corrections:
                candidate.update(review.corrections)
            try:
                validate_review_data(document.document_type, candidate)
            except ValueError as error:
                raise HTTPException(status_code=422, detail=str(error)) from error

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
            reviewer=request.state.actor.id,
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
                actor_id=request.state.actor.id,
                message=f"Document was {review.decision}",
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
async def upload_policy(
    request: Request,
    response: Response,
    file: Annotated[UploadFile, File()],
):

    file_bytes, file_type, content_type = await read_upload(file)

    policy_hash = calculate_file_hash(file_bytes)

    with SessionLocal() as db:

        duplicate_statement = (
            select(PolicyDocument)
            .where(
                PolicyDocument.file_hash == policy_hash,
                PolicyDocument.organization_id == request.state.actor.organization_id
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

        if processing_mode() != "inline":
            from app.jobs.queue import enqueue
            path = save_policy_file(file_bytes, file.filename, policy_id)
            policy = PolicyDocument(id=policy_id, organization_id=request.state.actor.organization_id,
                owner_id=request.state.actor.id, original_filename=file.filename, stored_file_path=path,
                mime_type=content_type, file_hash=policy_hash, rule_extraction_status="queued")
            db.add(policy)
            job = enqueue(db, "policy", policy_id, request.state.actor)
            from app.rag.indexing import request_index
            request_index(db, policy_id, request.state.actor)
            db.commit()
            response.status_code = 202
            return {"policy_id": policy_id, "filename": file.filename, "extraction_method": "queued",
                    "text_length": 0, "chunks_created": 0, "job_id": job.id,
                    "rule_extraction": {"status": "queued", "message": "Policy queued for automatic extraction."}}

        try:
            extracted_text, extraction_method = await run_in_threadpool(
                extract_text, file_bytes=file_bytes, file_type=file_type,
            )
        except ValueError as error:
            raise HTTPException(400, "Policy parsing failed or exceeded budget.") from error

        stored_file_path = save_policy_file(
            file_bytes=file_bytes, original_filename=file.filename, policy_id=policy_id,
        )

        policy = PolicyDocument(
            id=policy_id,
            organization_id=request.state.actor.organization_id,
            owner_id=request.state.actor.id,
            original_filename=file.filename,
            stored_file_path=stored_file_path,
            mime_type=content_type,
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

    extraction = await run_in_threadpool(run_policy_extraction, policy_id)
    from app.rag.indexing import request_index
    with SessionLocal() as db:
        request_index(db, policy_id, request.state.actor)
        db.commit()
    return {
        "policy_id": policy_id,
        "filename": file.filename,
        "extraction_method": extraction_method,
        "text_length": len(extracted_text),
        "chunks_created": len(chunks),
        "rule_extraction": extraction,
    }


def run_policy_extraction(policy_id):
    from app.validation.policy_extraction import extract_whole_policy
    with SessionLocal() as db:
        return extract_whole_policy(db, policy_id)


@app.post("/policies/{policy_id}/rules/extract-all")
def extract_all_policy_rules(policy_id: str, request: Request):
    if processing_mode() != "inline":
        from app.jobs.queue import enqueue
        with SessionLocal() as db:
            job = enqueue(db, "policy", policy_id, request.state.actor)
            if job.state in {"completed", "failed"}:
                job.state, job.attempts, job.error = "queued", 0, None
                job.actor_id = request.state.actor.id
                from app.database.models import utc_now_naive
                job.available_at = utc_now_naive()
            db.get(PolicyDocument, policy_id).rule_extraction_status = "queued"
            db.commit()
            return {"status": job.state, "job_id": job.id, "message": "Policy processing queued."}
    return run_policy_extraction(policy_id)


@app.post("/policies/{policy_id}/rules/approve-all")
def approve_all_policy_rules(policy_id: str, request: Request,
                             rule_ids: Annotated[list[str], Body(embed=True, min_length=1, max_length=100)]):
    from app.validation.rule_review_service import approve_policy_rules
    with SessionLocal() as db:
        try:
            return approve_policy_rules(db, policy_id, rule_ids, request.state.actor.id)
        except LookupError as error:
            raise HTTPException(404, "Policy rule not found.") from error
        except ValueError as error:
            raise HTTPException(409, str(error)) from error
@app.post("/documents/{document_id}/validate-policy", deprecated=True)
def validate_document_policy(document_id: str):
    """Retired model-led path: official decisions use approved rules only."""
    raise HTTPException(
        status_code=410,
        detail="Model-led validation is retired. Use validate-approved-policy after document review.",
    )

@app.post("/documents/{document_id}/validate-approved-policy")
def validate_document_approved_policy(
    document_id: str,
    request: Request,
    policy_id: str = Body(..., embed=True, min_length=1),
):
    from app.validation.approved_rule_repository import (
        PolicyRuleIntegrityError,
    )
    from app.validation.document_policy_service import (
        validate_document_with_approved_rules,
    )

    with SessionLocal() as db:

        # Verify document exists.
        document = db.get(Document, document_id)

        if document is None:
            raise HTTPException(
                status_code=404,
                detail="Document not found",
            )

        # Verify selected policy exists.
        policy = require_policy(db, policy_id, request.state.actor)

        if policy is None:
            raise HTTPException(
                status_code=404,
                detail="Policy not found",
            )

        try:
            return validate_document_with_approved_rules(
                db=db,
                document_id=document_id,
                policy_id=policy_id,
            )

        except PolicyRuleIntegrityError as error:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Approved policy rules contain invalid "
                    "data or evidence. Review is required."
                ),
            ) from error

        except ValueError as error:
            raise HTTPException(
                status_code=409,
                detail=str(error),
            ) from error

@app.post("/policies/{policy_id}/rules/extract-candidates")
def extract_policy_candidates(
    policy_id: str,
    chunk_index: int = Body(0, embed=True, ge=0),
):
    import logging

    from app.llm.factory import get_llm_provider
    from app.validation.candidate_rule_service import (
        extract_and_store_candidates,
    )

    with SessionLocal() as db:
        try:
            provider = get_llm_provider()

            return extract_and_store_candidates(
                db=db,
                policy_id=policy_id,
                chunk_index=chunk_index,
                provider=provider,
            )

        except LookupError as error:
            raise HTTPException(
                status_code=404,
                detail=str(error),
            ) from error

        except Exception as error:
            db.rollback()

            logging.getLogger(__name__).error(
                "Candidate rule extraction failed."
            )

            raise HTTPException(
                status_code=503,
                detail="Policy rule extraction failed.",
            ) from error

@app.get("/policies/{policy_id}/rules")
def list_policy_rules(policy_id: str):
    from app.database.models import StoredPolicyRule

    with SessionLocal() as db:
        policy = db.get(PolicyDocument, policy_id)

        if policy is None:
            raise HTTPException(
                status_code=404,
                detail="Policy not found.",
            )

        statement = (
            select(StoredPolicyRule)
            .where(StoredPolicyRule.policy_id == policy_id)
            .order_by(StoredPolicyRule.rule_id)
        )

        stored_rules = db.scalars(statement).all()

        return {
            "policy_id": policy_id,
            "total_rules": len(stored_rules),
            "extraction_status": policy.rule_extraction_status,
            "extraction_message": policy.rule_extraction_message,
            "rules": [
                {
                    "id": rule.id,
                    "rule_id": rule.rule_id,
                    "rule_data": rule.rule_data,
                    "verification_status": rule.verification_status,
                    "approval_status": rule.approval_status,
                    "approved_by": rule.approved_by,
                    "approved_by_name": user_label(db, rule.approved_by, policy.organization_id) if rule.approved_by else None,
                }
                for rule in stored_rules
            ],
        }

@app.post("/policies/{policy_id}/rules/{stored_rule_id}/review")
def review_candidate_policy_rule(
    policy_id: str,
    stored_rule_id: str,
    request: Request,
    decision: Literal["approve", "reject"] = Body(...),
    notes: str | None = Body(None),
    x_dev_review_token: str | None = Header(default=None),
):
    import logging
    import os
    import secrets

    from dotenv import load_dotenv

    from app.validation.rule_review_service import review_policy_rule

    load_dotenv()

    # Disabled unless explicitly enabled for local development.
    if os.getenv("ENABLE_DEV_POLICY_REVIEW") != "true":
        raise HTTPException(status_code=404, detail="Not found.")

    # Never expose this temporary approval route remotely.
    if (
        request.client is None
        or request.client.host not in {"127.0.0.1", "::1"}
    ):
        raise HTTPException(status_code=403, detail="Local access only.")

    expected_token = os.getenv("DEV_REVIEW_TOKEN")

    if (
        not expected_token
        or not x_dev_review_token
        or not secrets.compare_digest(
            x_dev_review_token,
            expected_token,
        )
    ):
        raise HTTPException(status_code=403, detail="Access denied.")

    reviewer = request.state.actor.id

    with SessionLocal() as db:
        try:
            return review_policy_rule(
                db=db,
                policy_id=policy_id,
                stored_rule_id=stored_rule_id,
                decision=decision,
                reviewer=reviewer,
                notes=notes,
            )

        except LookupError as error:
            db.rollback()
            raise HTTPException(
                status_code=404,
                detail=str(error),
            ) from error

        except ValueError as error:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail=str(error),
            ) from error

        except Exception as error:
            db.rollback()
            logging.getLogger(__name__).error(
                "Policy rule review failed."
            )
            raise HTTPException(
                status_code=500,
                detail="Unable to review policy rule.",
            ) from error


@app.get("/policies")
def list_policies(request: Request):
    with SessionLocal() as db:
        return [{"policy_id": p.id, "filename": p.original_filename, "added_at": p.created_at}
                for p in db.scalars(select(PolicyDocument).where(
                    PolicyDocument.organization_id == request.state.actor.organization_id)).all()]


@app.post("/policies/{policy_id}/rules/{stored_rule_id}/decision")
def decide_policy_rule(policy_id: str, stored_rule_id: str, request: Request,
                       decision: Literal["approve", "reject"] = Body(...), notes: str | None = Body(None)):
    from app.validation.rule_review_service import review_policy_rule
    with SessionLocal() as db:
        try:
            return review_policy_rule(db, policy_id, stored_rule_id, decision, request.state.actor.id, notes)
        except LookupError as error:
            raise HTTPException(404, "Policy rule not found.") from error
        except ValueError as error:
            raise HTTPException(409, str(error)) from error


@app.get("/policies/{policy_id}/original")
def get_original_policy(policy_id: str, request: Request):
    with SessionLocal() as db:
        policy = require_policy(db, policy_id, request.state.actor)
        path = Path(policy.stored_file_path)
        if not path.resolve().is_relative_to((policy_storage.POLICY_ROOT / policy_id).resolve()) or not path.is_file():
            raise HTTPException(404, "Original policy not found.")
        return FileResponse(path, media_type=policy.mime_type or "application/octet-stream", filename=policy.original_filename)
