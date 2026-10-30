"""Scoped processing status and explicit retry; job IDs are never access grants."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select

from app.auth.security import (
    authorize_request,
    require_document,
    require_policy,
    session_factory,
)
from app.database.models import ProcessingJob, utc_now_naive
from app.jobs.queue import enqueue

router = APIRouter(dependencies=[Depends(authorize_request)])


def resource_job(request, resource_id, kind, retry=False):
    with session_factory(request)() as db:
        resource = (require_document if kind == "document" else require_policy)(
            db, resource_id, request.state.actor
        )
        job = db.scalar(
            select(ProcessingJob).where(
                ProcessingJob.resource_id == resource_id, ProcessingJob.kind == kind
            )
        )
        if retry:
            if job is None:
                state = (
                    resource.processing_status
                    if kind == "document"
                    else resource.rule_extraction_status
                )
                if state != "failed":
                    raise HTTPException(409, "Only failed processing can be retried.")
                job = enqueue(db, kind, resource_id, request.state.actor)
            elif job.state != "failed":
                raise HTTPException(409, "Only a failed job can be retried.")
            else:
                job.state, job.attempts, job.error = "queued", 0, None
                job.available_at = utc_now_naive()
                job.actor_id = request.state.actor.id
            if kind == "document":
                resource.processing_status, resource.review_status = (
                    "queued",
                    "processing",
                )
            else:
                resource.rule_extraction_status = "queued"
            db.commit()
        if job is None:
            state = (
                resource.processing_status
                if kind == "document"
                else resource.rule_extraction_status
            )
            return {"job_id": None, "state": state, "attempts": 0, "error": None}
        return {
            "job_id": job.id,
            "state": job.state,
            "attempts": job.attempts,
            "max_attempts": job.max_attempts,
            "error": job.error,
            "updated_at": job.updated_at,
        }


@router.get("/documents/{resource_id}/processing")
def document_status(resource_id: str, request: Request):
    return resource_job(request, resource_id, "document")


@router.post("/documents/{resource_id}/processing/retry")
def document_retry(resource_id: str, request: Request):
    return resource_job(request, resource_id, "document", True)


@router.get("/policies/{resource_id}/processing")
def policy_status(resource_id: str, request: Request):
    return resource_job(request, resource_id, "policy")


@router.post("/policies/{resource_id}/processing/retry")
def policy_retry(resource_id: str, request: Request):
    return resource_job(request, resource_id, "policy", True)
