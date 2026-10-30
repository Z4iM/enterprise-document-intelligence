"""At-least-once claims; fenced transactional writes prevent stale-worker commits."""

import uuid
from datetime import timedelta

from sqlalchemy import and_, or_, select, update

from app.database.models import (
    Document,
    PolicyDocument,
    PolicySearchIndex,
    ProcessingJob,
    SpecialistWorkflow,
    utc_now_naive,
)

LEASE_SECONDS = 180


def enqueue(db, kind, resource_id, actor):
    existing = db.scalar(
        select(ProcessingJob).where(
            ProcessingJob.kind == kind, ProcessingJob.resource_id == resource_id
        )
    )
    if existing:
        return existing
    job = ProcessingJob(
        id=str(uuid.uuid4()),
        kind=kind,
        resource_id=resource_id,
        organization_id=actor.organization_id,
        actor_id=actor.id,
        state="queued",
    )
    db.add(job)
    db.flush()
    return job


def eligible(now):
    return or_(
        and_(
            ProcessingJob.state.in_(["queued", "retry_wait"]),
            ProcessingJob.available_at <= now,
        ),
        and_(ProcessingJob.state == "running", ProcessingJob.lease_until <= now),
    )


def claim(sessions):
    now = utc_now_naive()
    with sessions() as db:
        # An interrupted final attempt must become terminal rather than remain running forever.
        exhausted = db.scalars(
            select(ProcessingJob).where(
                eligible(now), ProcessingJob.attempts >= ProcessingJob.max_attempts
            )
        ).all()
        for job in exhausted:
            changed = db.execute(
                update(ProcessingJob)
                .where(ProcessingJob.id == job.id, eligible(now))
                .values(
                    state="failed",
                    error="Processing attempt budget exhausted.",
                    lease_token=None,
                    lease_until=None,
                    updated_at=now,
                )
            ).rowcount
            if changed:
                resource = db.get(
                    SpecialistWorkflow
                    if job.kind == "specialist"
                    else Document
                    if job.kind == "document"
                    else PolicyDocument,
                    job.resource_id,
                )
                if resource and resource.organization_id == job.organization_id:
                    if job.kind == "specialist":
                        resource.status = "failed"
                    elif job.kind == "document":
                        resource.processing_status, resource.review_status = (
                            "failed",
                            "needs_review",
                        )
                    elif job.kind == "policy_index":
                        index = db.get(PolicySearchIndex, job.resource_id)
                        if index and index.enabled:
                            index.state = "failed"
                    else:
                        resource.rule_extraction_status = "failed"
        query = (
            select(ProcessingJob.id)
            .where(eligible(now), ProcessingJob.attempts < ProcessingJob.max_attempts)
            .order_by(ProcessingJob.created_at)
            .limit(1)
        )
        if db.get_bind().dialect.name == "postgresql":
            query = query.with_for_update(skip_locked=True)
        identifier = db.scalar(query)
        if identifier is None:
            db.commit()
            return None
        token = str(uuid.uuid4())
        changed = db.execute(
            update(ProcessingJob)
            .where(ProcessingJob.id == identifier, eligible(now))
            .values(
                state="running",
                attempts=ProcessingJob.attempts + 1,
                lease_token=token,
                lease_until=now + timedelta(seconds=LEASE_SECONDS),
                updated_at=now,
            )
        ).rowcount
        db.commit()
        return (identifier, token) if changed == 1 else None


def finish(db, job, token):
    # Business writes and this fence are committed in the SAME transaction.
    changed = db.execute(
        update(ProcessingJob)
        .where(
            ProcessingJob.id == job.id,
            ProcessingJob.state == "running",
            ProcessingJob.lease_token == token,
            ProcessingJob.lease_until > utc_now_naive(),
        )
        .values(
            state="completed",
            error=None,
            lease_token=None,
            lease_until=None,
            updated_at=utc_now_naive(),
        )
    ).rowcount
    if changed != 1:
        db.rollback()
        raise RuntimeError("Worker lease expired.")
    db.commit()


def fail(sessions, identifier, token):
    with sessions() as db:
        job = db.get(ProcessingJob, identifier)
        if job is None or job.lease_token != token or job.state != "running":
            return
        terminal = job.attempts >= job.max_attempts
        changed = db.execute(
            update(ProcessingJob)
            .where(ProcessingJob.id == identifier, ProcessingJob.lease_token == token)
            .values(
                state="failed" if terminal else "retry_wait",
                lease_token=None,
                lease_until=None,
                error="Processing failed. Retry the job or check worker configuration.",
                available_at=utc_now_naive()
                + timedelta(seconds=min(60, 5 * 2**job.attempts)),
                updated_at=utc_now_naive(),
            )
        ).rowcount
        if changed:
            resource = db.get(
                SpecialistWorkflow
                if job.kind == "specialist"
                else Document
                if job.kind == "document"
                else PolicyDocument,
                job.resource_id,
            )
            if resource and resource.organization_id == job.organization_id:
                if job.kind == "specialist":
                    resource.status = "failed" if terminal else "retry_wait"
                elif job.kind == "document":
                    resource.processing_status = "failed" if terminal else "retry_wait"
                    resource.review_status = "needs_review"
                elif job.kind == "policy_index":
                    index = db.get(PolicySearchIndex, job.resource_id)
                    if index and index.enabled:
                        index.state = "failed" if terminal else "queued"
                else:
                    resource.rule_extraction_status = (
                        "failed" if terminal else "retry_wait"
                    )
                    resource.rule_extraction_message = (
                        "Processing failed; check the job status."
                    )
        db.commit()
