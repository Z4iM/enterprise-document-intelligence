import logging
import os
import secrets

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from google import genai
from pydantic import BaseModel, Field

from app.agents.verified_investigation import (
    run_verified_investigation,
)
from app.auth.security import authorize_request, authorized_scope
from app.database.database import SessionLocal

load_dotenv()

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/agent",
    dependencies=[Depends(authorize_request)],
    tags=["Investigation Agent"],
)


class InvestigationRequest(BaseModel):
    # Selections narrow session-derived permissions; they never grant access.
    model_config = {"extra": "forbid"}

    question: str = Field(
        min_length=1,
        max_length=1500,
    )
    document_id: str | None = Field(
        default=None, min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$"
    )
    policy_id: str | None = Field(
        default=None, min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$"
    )


def require_dev_agent_access(
    request: Request,
    token: str | None,
) -> None:
    """Protect the temporary local-development API."""

    if os.getenv("EDI_ENABLE_DEV_AGENT") != "true":
        raise HTTPException(
            status_code=404,
            detail="Not found.",
        )

    if request.client is None or request.client.host not in {"127.0.0.1", "::1"}:
        raise HTTPException(
            status_code=403,
            detail="Local access only.",
        )

    expected_token = os.getenv("EDI_DEV_AGENT_TOKEN")

    if (
        not expected_token
        or not token
        or not secrets.compare_digest(
            token,
            expected_token,
        )
    ):
        raise HTTPException(
            status_code=403,
            detail="Access denied.",
        )


@router.post("/investigate")
def investigate_document(
    payload: InvestigationRequest,
    request: Request,
    x_edi_agent_token: str | None = Header(default=None),
):
    """
    Run one locally authorized EDI investigation.

    Optional document/policy selections only narrow server-derived account permissions.
    """

    require_dev_agent_access(
        request=request,
        token=x_edi_agent_token,
    )

    question = payload.question.strip()

    if not question:
        raise HTTPException(
            status_code=422,
            detail="Question cannot be empty.",
        )

    if bool(payload.document_id) != bool(payload.policy_id):
        raise HTTPException(422, "Select both a document and a policy.")

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="Gemini is not configured.",
        )

    model = os.getenv(
        "GEMINI_MODEL",
        "gemini-3.5-flash-lite",
    )

    with SessionLocal() as db:
        allowed_documents, allowed_policies = authorized_scope(db, request.state.actor)
        if payload.document_id and payload.policy_id:
            if (
                payload.document_id not in allowed_documents
                or payload.policy_id not in allowed_policies
            ):
                raise HTTPException(404, "Selected document or policy is unavailable.")
            allowed_documents = {payload.document_id}
            allowed_policies = {payload.policy_id}
        if not allowed_documents or not allowed_policies:
            raise HTTPException(
                409,
                "Upload an accessible document and policy before starting an investigation.",
            )
        if len(allowed_documents) > 50 or len(allowed_policies) > 50:
            raise HTTPException(422, "Choose a document and policy to investigate.")
        client = None

        try:
            client = genai.Client(api_key=api_key, http_options={"timeout": 30000})

            result = run_verified_investigation(
                question=question,
                client=client,
                model=model,
                allowed_document_ids=allowed_documents,
                allowed_policy_ids=allowed_policies,
                db=db,
            )

        except Exception as error:
            logger.error(
                "Agent investigation failed (failure_type=%s).", type(error).__name__
            )

            raise HTTPException(
                status_code=502,
                detail="Investigation service unavailable.",
            ) from error

        finally:
            if client is not None:
                client.close()

    return result
