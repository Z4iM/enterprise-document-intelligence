"""Owned synthetic Compose fixture only; verifies specialist pause/restart/resume."""

import argparse
import time

from sqlalchemy import select

from app.auth.security import Principal
from app.database.database import SessionLocal
from app.database.models import (
    Document,
    PolicyDocument,
    ProcessingJob,
    SpecialistWorkflow,
    User,
    utc_now_naive,
)
from app.jobs.queue import enqueue
from app.jobs.smoke import DOCUMENT, EMPLOYEE, ORG, POLICY, REVIEWER

IDENTIFIER = "edi-smoke-specialists"


def run_smoke(*, verify=False, sessions=SessionLocal):
    with sessions() as db:
        if (
            set(db.scalars(select(User.id))) != {EMPLOYEE, REVIEWER}
            or set(db.scalars(select(Document.id))) != {DOCUMENT}
            or set(db.scalars(select(PolicyDocument.id))) != {POLICY}
        ):
            raise RuntimeError(
                "Specialist smoke refused: non-fixture accounts/resources exist."
            )
        run = db.get(SpecialistWorkflow, IDENTIFIER)
        if not verify:
            if run is not None:
                raise RuntimeError("Use a fresh isolated verification project.")
            run = SpecialistWorkflow(
                id=IDENTIFIER,
                organization_id=ORG,
                owner_id=EMPLOYEE,
                document_id=DOCUMENT,
                policy_id=POLICY,
                question="Synthetic restart investigation",
                request_key="synthetic-restart-key",
            )
            db.add(run)
            db.flush()
            enqueue(db, "specialist", run.id, Principal(EMPLOYEE, ORG, "employee"))
        else:
            if (
                run is None
                or run.status != "waiting_for_document_review"
                or not run.checkpoint_thread
            ):
                raise RuntimeError("Persisted paused specialist fixture missing.")
            job = db.scalar(
                select(ProcessingJob).where(
                    ProcessingJob.kind == "specialist",
                    ProcessingJob.resource_id == run.id,
                )
            )
            if job is None or job.state != "completed":
                raise RuntimeError("Paused specialist claim did not complete.")
            job.state, job.attempts, job.error, job.available_at = (
                "queued",
                0,
                None,
                utc_now_naive(),
            )
            run.status, run.resumes = "queued", 1
        db.commit()
    for _ in range(90):
        with sessions() as db:
            job = db.scalar(
                select(ProcessingJob).where(
                    ProcessingJob.kind == "specialist",
                    ProcessingJob.resource_id == IDENTIFIER,
                )
            )
            run = db.get(SpecialistWorkflow, IDENTIFIER)
            if job.state == "completed":
                assert run.status == (
                    "completed" if verify else "waiting_for_document_review"
                )
                assert run.checkpoint_thread
                if verify:
                    assert run.result["evaluation"]["status"] == "requires_approval"
                    assert run.result["model_calls"] == 0
                return {
                    "specialist_checkpoint": "resumed"
                    if verify
                    else "waiting_for_review",
                    "real_model_calls": 0,
                }
            if job.state == "failed":
                raise RuntimeError("Synthetic specialist execution failed.")
        time.sleep(0.5)
    raise RuntimeError("Synthetic specialist worker timed out.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    print(run_smoke(verify=parser.parse_args().verify))


if __name__ == "__main__":
    main()
