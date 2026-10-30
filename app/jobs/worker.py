"""Single bounded worker; safe to run multiple processes against PostgreSQL."""

import logging
import signal
import threading

from app.database.database import SessionLocal
from app.database.models import ProcessingJob
from app.jobs import processors
from app.jobs.queue import claim, fail, finish


def run_once(sessions=SessionLocal, handler=None):
    leased = claim(sessions)
    if leased is None:
        return False
    identifier, token = leased
    try:
        with sessions() as db:
            job = db.get(ProcessingJob, identifier)
            (handler or processors.process)(db, job)
            finish(db, job, token)
    except Exception as error:  # noqa: BLE001 - queue records redacted failures for bounded retry.
        logging.getLogger(__name__).error(
            "Processing job failed (%s).", type(error).__name__
        )
        fail(sessions, identifier, token)
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
    stop = threading.Event()
    for name in ("SIGINT", "SIGTERM"):
        signal.signal(getattr(signal, name), lambda *_: stop.set())
    serve(stop)


if __name__ == "__main__":
    main()
