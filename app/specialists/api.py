"""Session/scoped local-only workflow intake; IDs/idempotency keys are never grants."""

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.auth.security import authorize_request, session_factory, throttle
from app.database.models import ProcessingJob, SpecialistWorkflow, utc_now_naive
from app.jobs.queue import enqueue
from app.review.documentation import documentation_checklist
from app.specialists.graph import (
    current_scope,
    document_fingerprint,
    policy_fingerprint,
)
from app.validation.approved_rule_repository import PolicyRuleIntegrityError
from app.workflows.api import require_dev_access

router = APIRouter(
    prefix="/specialist-workflows", dependencies=[Depends(authorize_request)]
)


def scoped_run(db, identifier, actor):
    run = db.get(SpecialistWorkflow, identifier)
    if (
        run is None
        or run.organization_id != actor.organization_id
        or (actor.role == "employee" and run.owner_id != actor.id)
    ):
        raise HTTPException(404, "Workflow not found.")
    current_scope(db, actor.id, run.document_id, run.policy_id)
    return run


def public_run(db, run, actor):
    _, document = current_scope(db, actor.id, run.document_id, run.policy_id)
    result = dict(run.result or {})
    stale = result.get("document_fingerprint") not in {
        None,
        document_fingerprint(document),
    }
    if result.get("policy_fingerprint"):
        try:
            stale |= result["policy_fingerprint"] != policy_fingerprint(
                db, run.policy_id
            )
        except PolicyRuleIntegrityError:
            stale = True
    if result.get("documentation") and not stale:
        stale |= result["documentation"] != documentation_checklist(
            db, actor, run.document_id, run.policy_id
        )
    if stale:
        result["evaluation"], result["documentation"] = {}, {}
    job = db.scalar(
        select(ProcessingJob).where(
            ProcessingJob.kind == "specialist", ProcessingJob.resource_id == run.id
        )
    )
    status = (
        job.state
        if job and job.state in {"queued", "running", "retry_wait", "failed"}
        else "needs_revalidation"
        if stale
        else run.status
    )
    return {
        "workflow_id": run.id,
        "document_id": run.document_id,
        "policy_id": run.policy_id,
        "question": run.question,
        "status": status,
        "result": result,
        "resumes": run.resumes,
        "created_at": run.created_at,
        "error": job.error if job and job.state == "failed" else None,
    }


class StartSpecialists(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    policy_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    question: str = Field(min_length=1, max_length=1500)
    request_key: str = Field(min_length=8, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")

    @field_validator("question")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("Question required.")
        return value.strip()


@router.post("", status_code=202)
def start(
    body: StartSpecialists,
    request: Request,
    response: Response,
    x_edi_workflow_token: str | None = Header(default=None),
):
    require_dev_access(request, x_edi_workflow_token)
    actor = request.state.actor
    with session_factory(request)() as db:
        current_scope(db, actor.id, body.document_id, body.policy_id)
        statement = select(SpecialistWorkflow).where(
            SpecialistWorkflow.organization_id == actor.organization_id,
            SpecialistWorkflow.owner_id == actor.id,
            SpecialistWorkflow.request_key == body.request_key,
        )
        existing = db.scalar(statement)
        if existing is None:
            throttle(db, "specialist-start:" + actor.id, 10, 60)
            run = SpecialistWorkflow(
                id=str(uuid.uuid4()),
                organization_id=actor.organization_id,
                owner_id=actor.id,
                document_id=body.document_id,
                policy_id=body.policy_id,
                question=body.question,
                request_key=body.request_key,
            )
            db.add(run)
            try:
                db.flush()
                enqueue(db, "specialist", run.id, actor)
                db.commit()
                existing = run
            except IntegrityError:
                db.rollback()
                existing = db.scalar(statement)
                if existing is None:
                    raise HTTPException(
                        409, "Concurrent workflow request; retry."
                    ) from None
        else:
            response.status_code = 200
        if (existing.document_id, existing.policy_id, existing.question) != (
            body.document_id,
            body.policy_id,
            body.question,
        ):
            raise HTTPException(
                409, "Request key already belongs to a different workflow request."
            )
        return public_run(db, existing, actor)


@router.get("")
def listing(request: Request, x_edi_workflow_token: str | None = Header(default=None)):
    require_dev_access(request, x_edi_workflow_token)
    actor = request.state.actor
    with session_factory(request)() as db:
        statement = select(SpecialistWorkflow).where(
            SpecialistWorkflow.organization_id == actor.organization_id
        )
        if actor.role == "employee":
            statement = statement.where(SpecialistWorkflow.owner_id == actor.id)
        rows = db.scalars(
            statement.order_by(SpecialistWorkflow.created_at.desc()).limit(50)
        ).all()
        result = []
        for run in rows:
            try:
                scoped_run(db, run.id, actor)
                job = db.scalar(
                    select(ProcessingJob).where(
                        ProcessingJob.kind == "specialist",
                        ProcessingJob.resource_id == run.id,
                    )
                )
                result.append(
                    {
                        "workflow_id": run.id,
                        "document_id": run.document_id,
                        "policy_id": run.policy_id,
                        "question": run.question,
                        "status": job.state
                        if job
                        and job.state in {"queued", "running", "retry_wait", "failed"}
                        else run.status,
                        "resumes": run.resumes,
                        "created_at": run.created_at,
                    }
                )
            except HTTPException:
                continue
        return result


@router.get("/{identifier}")
def get_run(
    identifier: str,
    request: Request,
    x_edi_workflow_token: str | None = Header(default=None),
):
    require_dev_access(request, x_edi_workflow_token)
    with session_factory(request)() as db:
        return public_run(
            db, scoped_run(db, identifier, request.state.actor), request.state.actor
        )


class ResumeSpecialists(BaseModel):
    model_config = ConfigDict(extra="forbid")


@router.post("/{identifier}/resume", status_code=202)
def resume(
    identifier: str,
    request: Request,
    body: ResumeSpecialists | None = None,
    x_edi_workflow_token: str | None = Header(default=None),
):
    require_dev_access(request, x_edi_workflow_token)
    actor = request.state.actor
    with session_factory(request)() as db:
        run = scoped_run(db, identifier, actor)
        state = public_run(db, run, actor)
        if (
            run.resumes >= 8
            or state["status"] in {"queued", "running", "retry_wait"}
            or (run.status == "completed" and state["status"] != "needs_revalidation")
        ):
            raise HTTPException(
                409, "Workflow is not resumable or its replay budget is exhausted."
            )
        changed = db.execute(
            update(SpecialistWorkflow)
            .where(
                SpecialistWorkflow.id == run.id,
                SpecialistWorkflow.resumes == run.resumes,
            )
            .values(
                resumes=run.resumes + 1, status="queued", updated_at=utc_now_naive()
            )
        ).rowcount
        changed_job = db.execute(
            update(ProcessingJob)
            .where(
                ProcessingJob.kind == "specialist",
                ProcessingJob.resource_id == run.id,
                ProcessingJob.state.in_(["completed", "failed"]),
            )
            .values(
                state="queued",
                attempts=0,
                error=None,
                actor_id=actor.id,
                lease_token=None,
                lease_until=None,
                available_at=utc_now_naive(),
            )
        ).rowcount
        if changed != 1 or changed_job != 1:
            db.rollback()
            raise HTTPException(409, "Concurrent resume; refresh workflow status.")
        db.commit()
        return public_run(db, run, actor)
