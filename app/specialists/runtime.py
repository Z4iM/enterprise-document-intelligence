"""Lease-isolated checkpoint branches: only a fenced DB commit publishes a new head."""

import copy
import os
import time
from collections import defaultdict
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from sqlalchemy.orm import sessionmaker

from app.database.models import SpecialistWorkflow, utc_now_naive
from app.specialists.graph import build_graph, current_scope


def checkpoint_path():
    return Path(os.getenv("EDI_DATA_ROOT", "data")) / "specialist_checkpoints.sqlite"


def execute_workflow(db, job):
    if os.getenv("EDI_ENABLE_DEV_WORKFLOWS") != "true":
        raise ValueError("Specialist workflows are disabled.")
    run = db.get(SpecialistWorkflow, job.resource_id)
    if run is None or run.organization_id != job.organization_id:
        raise ValueError("Workflow unavailable.")
    actor, _ = current_scope(db, job.actor_id, run.document_id, run.policy_id)
    if actor.organization_id != run.organization_id or (
        actor.role == "employee" and run.owner_id != actor.id
    ):
        raise ValueError("Workflow access revoked.")
    path = checkpoint_path()
    if run.checkpoint_thread and not path.is_file():
        raise ValueError("Required workflow checkpoint backup is missing.")
    path.parent.mkdir(parents=True, exist_ok=True)
    sessions = sessionmaker(bind=db.get_bind(), autoflush=False)
    thread = run.id + ":" + job.lease_token
    config = {
        "configurable": {"thread_id": thread, "checkpoint_ns": ""},
        "recursion_limit": 16,
    }
    with SqliteSaver.from_conn_string(str(path)) as saver:
        graph = build_graph(
            saver,
            sessions=sessions,
            actor_id=job.actor_id,
            deadline=time.monotonic() + 90,
        )
        previous = (
            saver.get_tuple({"configurable": {"thread_id": run.checkpoint_thread}})
            if run.checkpoint_thread
            else None
        )
        if run.checkpoint_thread and previous is None:
            raise ValueError(
                "Canonical workflow checkpoint is missing; restore its backup."
            )
        if previous is not None:
            # Clone the latest checkpoint and pending interrupts, never share an attempt's
            # writable thread with another lease. Failed/stale branches remain unpublished.
            cloned = saver.put(
                config,
                copy.deepcopy(previous.checkpoint),
                copy.deepcopy(previous.metadata),
                previous.checkpoint["channel_versions"],
            )
            writes = defaultdict(list)
            for task_id, channel, value in previous.pending_writes or []:
                writes[task_id].append((channel, value))
            for task_id, values in writes.items():
                saver.put_writes(cloned, values, task_id)
            snapshot = graph.get_state(config)
            payload = (
                Command(resume="canonical_review_recheck")
                if snapshot.next
                else {
                    "document_id": run.document_id,
                    "policy_id": run.policy_id,
                    "question": run.question,
                    "evaluation": {},
                    "documentation": {},
                }
            )
        else:
            payload = {
                "document_id": run.document_id,
                "policy_id": run.policy_id,
                "question": run.question,
            }
        graph.invoke(payload, config)
        snapshot = graph.get_state(config)
        values = dict(snapshot.values)
    run.checkpoint_thread = thread
    run.status, run.result, run.updated_at = values["status"], values, utc_now_naive()
    # No commit: queue.finish atomically commits these fields with the unexpired lease.
