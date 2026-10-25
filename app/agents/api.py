
import logging
import os
import secrets

from dotenv import load_dotenv
from fastapi import APIRouter, Header, HTTPException, Request
from google import genai
from pydantic import BaseModel, Field

from app.agents.verified_investigation import (
    run_verified_investigation,
)
from app.database.database import SessionLocal

load_dotenv()

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/agent",
    tags=["Investigation Agent"],
)


class InvestigationRequest(BaseModel):
    question: str = Field(
        min_length=1,
        max_length=1500,
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

    if (
        request.client is None
        or request.client.host not in {"127.0.0.1", "::1"}
    ):
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


def read_allowed_ids(env_name: str) -> set[str]:
    """Read trusted resource IDs from server configuration."""

    raw = os.getenv(env_name, "")

    return {
        value.strip()
        for value in raw.split(",")
        if value.strip()
    }


@router.post("/investigate")
def investigate_document(
    payload: InvestigationRequest,
    request: Request,
    x_edi_agent_token: str | None = Header(default=None),
):
    """
    Run one locally authorized EDI investigation.

    User input contains only the question.
    Document and policy permissions are server-controlled.
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

    allowed_documents = read_allowed_ids(
        "EDI_DEV_AGENT_DOCUMENT_IDS"
    )

    allowed_policies = read_allowed_ids(
        "EDI_DEV_AGENT_POLICY_IDS"
    )

    if not allowed_documents or not allowed_policies:
        raise HTTPException(
            status_code=503,
            detail="Investigation scope is not configured.",
        )

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
        client = None

        try:
            client = genai.Client(api_key=api_key)

            result = run_verified_investigation(
                question=question,
                client=client,
                model=model,
                allowed_document_ids=allowed_documents,
                allowed_policy_ids=allowed_policies,
                db=db,
            )

        except Exception as error:
            logger.exception(
                "Agent investigation failed."
            )

            raise HTTPException(
                status_code=502,
                detail="Investigation service unavailable.",
            ) from error

        finally:
            if client is not None:
                client.close()

    return result
