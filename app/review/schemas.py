from typing import Literal, Optional
from pydantic import BaseModel, Field


class ReviewRequest(BaseModel):

    decision: Literal[
        "approved",
        "corrected",
        "rejected"
    ]

    reviewer: str | None = None

    corrections: dict | None = None

    notes: str | None = None
class PolicyValidationSchema(BaseModel):
    status: str

    summary: Optional[str] = None

    violations: list[str] = Field(
        default_factory=list
    )

    required_actions: list[str] = Field(
        default_factory=list
    )

    source_chunk_ids: list[str] = Field(
        default_factory=list
    )