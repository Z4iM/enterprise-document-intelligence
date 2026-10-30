
import os
import secrets
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from pydantic import BaseModel, Field

from app.auth.security import authorize_request, require_document, require_policy
from app.database.models import WorkflowRun
from app.workflows import document_policy_graph as workflow
from app.workflows.durable_review_graph import (
    build_durable_review_graph,
)

load_dotenv()

router = APIRouter(prefix="/workflows", tags=["Workflows"], dependencies=[Depends(authorize_request)])

CHECKPOINT_PATH = Path(os.getenv("EDI_DATA_ROOT", "data")) / "langgraph_checkpoints.sqlite"


class StartWorkflowRequest(BaseModel):
    model_config = {"extra": "forbid"}
    document_id: str = Field(min_length=1, max_length=128)
    policy_id: str = Field(min_length=1, max_length=128)


def require_dev_access(request: Request, token: str | None):
    """Temporary local-development access protection."""

    if os.getenv("EDI_ENABLE_DEV_WORKFLOWS") != "true":
        raise HTTPException(
            status_code=404,
            detail="Not found.",
        )

    if (
        request.client is None
        or request.client.host not in {"127.0.0.1", "::1"}
    ):
        raise HTTPException(
            status_code=403,
            detail="Local access only.",
        )

    expected = os.getenv("EDI_DEV_WORKFLOW_TOKEN")

    if (
        not expected
        or not token
        or not secrets.compare_digest(token, expected)
    ):
        raise HTTPException(
            status_code=403,
            detail="Access denied.",
        )


@router.post("/start")
def start_workflow(
    payload: StartWorkflowRequest,
    request: Request,
    x_edi_workflow_token: str | None = Header(default=None),
):
    require_dev_access(request, x_edi_workflow_token)

    actor = request.state.actor
    with workflow.SessionLocal() as db:
        require_document(db, payload.document_id, actor)
        require_policy(db, payload.policy_id, actor)
        workflow_id = str(uuid.uuid4())
        db.add(WorkflowRun(id=workflow_id, organization_id=actor.organization_id, owner_id=actor.id,
                           document_id=payload.document_id, policy_id=payload.policy_id))
        db.commit()

    check_workflow_scope(workflow_id, request.state.actor)

    config = {
        "configurable": {
            "thread_id": workflow_id,
        }
    }

    CHECKPOINT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with SqliteSaver.from_conn_string(
        str(CHECKPOINT_PATH)
    ) as saver:
        graph = build_durable_review_graph(saver, principal=request.state.actor)

        result = graph.invoke(
            {
                "document_id": payload.document_id,
                "policy_id": payload.policy_id,
            },
            config=config,
        )

        snapshot = graph.get_state(config)

        if snapshot.next == ("wait_for_human_review",):
            status = "waiting_for_review"
        else:
            status = result.get(
                "workflow_status",
                "unknown",
            )

        evaluation = snapshot.values.get(
            "policy_evaluation"
        ) or {}

        actions = [
            item["action"]
            for item in evaluation.get(
                "required_actions",
                [],
            )
        ]

    return {
        "workflow_id": workflow_id,
        "document_id": payload.document_id,
        "policy_id": payload.policy_id,
        "status": status,
        "pending_nodes": list(snapshot.next),
        "required_actions": actions,
    }

@router.get("/{workflow_id}")
def get_workflow_status(
    workflow_id: str,
    request: Request,
    x_edi_workflow_token: str | None = Header(default=None),
):
    """Retrieve a saved workflow's current checkpoint status."""

    # Apply the same local-development access protection.
    require_dev_access(request, x_edi_workflow_token)

    check_workflow_scope(workflow_id, request.state.actor)

    config = {
        "configurable": {
            "thread_id": workflow_id,
        }
    }

    with SqliteSaver.from_conn_string(
        str(CHECKPOINT_PATH)
    ) as saver:

        # Verify this workflow actually exists.
        checkpoint = saver.get_tuple(config)

        if checkpoint is None:
            raise HTTPException(
                status_code=404,
                detail="Workflow not found.",
            )

        graph = build_durable_review_graph(saver, principal=request.state.actor)

        snapshot = graph.get_state(config)

        # Determine the workflow's current state.
        if snapshot.next == ("wait_for_human_review",):
            status = "waiting_for_review"

        elif snapshot.next:
            status = "pending"

        else:
            status = snapshot.values.get(
                "workflow_status",
                "unknown",
            )

        evaluation = snapshot.values.get(
            "policy_evaluation"
        ) or {}

        required_actions = [
            item["action"]
            for item in evaluation.get(
                "required_actions",
                [],
            )
        ]

        return {
            "workflow_id": workflow_id,
            "document_id": snapshot.values.get(
                "document_id"
            ),
            "policy_id": snapshot.values.get(
                "policy_id"
            ),
            "status": status,
            "pending_nodes": list(snapshot.next),
            "required_actions": required_actions,
        }

@router.post("/{workflow_id}/resume")
def resume_workflow(
    workflow_id: str,
    request: Request,
    x_edi_workflow_token: str | None = Header(default=None),
):
    """
    Resume an interrupted workflow.

    The resume signal does not grant approval.
    The graph reloads document status from SQLite.
    """

    require_dev_access(request, x_edi_workflow_token)

    if not CHECKPOINT_PATH.is_file():
        raise HTTPException(
            status_code=404,
            detail="Workflow not found.",
        )

    check_workflow_scope(workflow_id, request.state.actor)

    config = {
        "configurable": {
            "thread_id": workflow_id,
        }
    }

    with SqliteSaver.from_conn_string(
        str(CHECKPOINT_PATH)
    ) as saver:

        # 1. Ensure the workflow exists.
        if saver.get_tuple(config) is None:
            raise HTTPException(
                status_code=404,
                detail="Workflow not found.",
            )

        graph = build_durable_review_graph(saver, principal=request.state.actor)

        snapshot = graph.get_state(config)

        # 2. Only resume workflows awaiting human review.
        if snapshot.next != ("wait_for_human_review",):
            raise HTTPException(
                status_code=409,
                detail=(
                    "Workflow is not waiting for human review."
                ),
            )

        # 3. Resume the saved execution.
        # The graph MUST reload the real document status.
        graph.invoke(
            Command(resume="review_recorded"),
            config=config,
        )

        # 4. Retrieve the updated checkpoint.
        snapshot = graph.get_state(config)

        if snapshot.next == ("wait_for_human_review",):
            status = "waiting_for_review"

        elif snapshot.next:
            status = "pending"

        else:
            status = snapshot.values.get(
                "workflow_status",
                "unknown",
            )

        evaluation = snapshot.values.get(
            "policy_evaluation"
        ) or {}

        required_actions = [
            item["action"]
            for item in evaluation.get(
                "required_actions",
                [],
            )
        ]

        return {
            "workflow_id": workflow_id,
            "document_id": snapshot.values.get(
                "document_id"
            ),
            "policy_id": snapshot.values.get(
                "policy_id"
            ),
            "status": status,
            "pending_nodes": list(snapshot.next),
            "required_actions": required_actions,
        }


def check_workflow_scope(workflow_id, actor):
    if len(workflow_id) > 128:
        raise HTTPException(404, "Workflow not found.")
    with workflow.SessionLocal() as db:
        run = db.get(WorkflowRun, workflow_id)
        if run is None or run.organization_id != actor.organization_id or (
            actor.role == "employee" and run.owner_id != actor.id
        ):
            raise HTTPException(404, "Workflow not found.")
        require_document(db, run.document_id, actor)
        require_policy(db, run.policy_id, actor)
