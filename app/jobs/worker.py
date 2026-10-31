"""Single bounded worker; safe to run multiple processes against PostgreSQL."""

import logging
import signal
import threading

from app.database.database import SessionLocal
from app.database.models import ProcessingJob, utc_now_naive
from app.jobs import processors
from app.jobs.queue import claim, fail, finish
from app.observability.tracing import collection, configure_logging, persist, span


def run_once(sessions=SessionLocal, handler=None):
    leased = claim(sessions)
    if leased is None:
        return False
    identifier, token = leased
    with sessions() as db:
        job = db.get(ProcessingJob, identifier)
        if (
            job is None
            or job.state != "running"
            or job.lease_token != token
            or job.lease_until is None
            or job.lease_until <= utc_now_naive()
        ):
            return True
        trusted_trace, parent, organization = (
            job.trace_id,
            job.parent_span_id,
            job.organization_id,
        )
    with collection(
        trusted_trace=trusted_trace, parent=parent, organization_id=organization
    ) as collector:
        try:
            with span("job.execute") as item:
                try:
                    with sessions() as db:
                        job = db.get(ProcessingJob, identifier)
                        if (
                            job.state != "running"
                            or job.lease_token != token
                            or job.lease_until <= utc_now_naive()
                        ):
                            raise RuntimeError("Worker lease changed before execution.")
                        item.measurements = {
                            "attempt": job.attempts,
                            "queue_wait_ms": max(
                                0,
                                (utc_now_naive() - job.available_at).total_seconds()
                                * 1000,
                            ),
                        }
                        (handler or processors.process)(db, job)
                        finish(db, job, token)
                except Exception:  # noqa: BLE001 - queue records redacted bounded retries.
                    item.status = "error"
                    fail(sessions, identifier, token)
        finally:
            persist(collector, sessions)
    return True


def serve(stop, sessions=SessionLocal):
    while not stop.is_set():
        try:
            worked = run_once(sessions)
        except Exception as error:  # noqa: BLE001 - retry transient database connectivity without source logging.
            logging.getLogger(__name__).error(
                "Worker unavailable (%s).", type(error).__name__
            )
            worked = False
        stop.wait(0.1 if worked else 1)


def main():
    configure_logging()
    stop = threading.Event()
    for name in ("SIGINT", "SIGTERM"):
        signal.signal(getattr(signal, name), lambda *_: stop.set())
    serve(stop)


if __name__ == "__main__":
    main()
