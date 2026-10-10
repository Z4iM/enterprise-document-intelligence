from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class PolicyRule(BaseModel):
    rule_id: str
    category: str

    field: str

    operator: Literal[
        ">", ">=", "<", "<=", "=="
    ]

    threshold: Decimal = Field(ge=0)
    currency: str = "USD"

    action: Literal[
        "requires_approval",
        "requires_documentation",
        "policy_violation"
    ]

    approval_role: str | None = None
    source_quote: str | None = None
    source_chunk_id: str



class RuleEvaluation(BaseModel):
    rule_id: str
    applicable: bool
    # True: rule condition matched
    # False: condition did not match
    # None: cannot determine / not applicable
    triggered: bool | None

    status: Literal[
        "passed",
        "requires_approval",
        "requires_documentation",
        "policy_violation",
        "needs_review"
    ]

    explanation: str
