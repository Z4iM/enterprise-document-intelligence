
from sqlalchemy.orm import Session

from app.agents.tools.document_tools import inspect_document
from app.agents.tools.evaluation_tools import evaluate_document_policy
from app.agents.tools.policy_tools import get_policy_evidence

# Explicit allowlist: no dynamic imports, eval, or arbitrary calls.
TOOL_ARGUMENTS = {
    "inspect_document": {"document_id"},
    "get_policy_evidence": {"policy_id"},
    "evaluate_document_policy": {
        "document_id",
        "policy_id",
    },
}


def dispatch_tool_call(
    name: str,
    args: dict,
    *,
    allowed_document_ids: set[str],
    allowed_policy_ids: set[str],
    db: Session,
) -> dict:
    """
    Execute one permitted agent tool call.

    Tool name and args are untrusted model output.
    Permissions and database session are trusted inputs.

    No LLM-generated argument can override authorization.
    """

    # 1. Reject unknown tools.
    if name not in TOOL_ARGUMENTS:
        return {"status": "unknown_tool"}

    # 2. Require exactly the expected arguments.
    expected = TOOL_ARGUMENTS[name]

    if not isinstance(args, dict) or set(args) != expected:
        return {"status": "invalid_arguments"}

    # 3. Validate resource identifiers.
    for key in expected:
        value = args[key]

        if (
            not isinstance(value, str)
            or not value.strip()
            or len(value) > 128
        ):
            return {"status": "invalid_arguments"}

    # 4. Execute ONLY our approved Python tools.
    if name == "inspect_document":
        return inspect_document(
            document_id=args["document_id"],
            allowed_document_ids=allowed_document_ids,
            db=db,
        )

    if name == "get_policy_evidence":
        return get_policy_evidence(
            policy_id=args["policy_id"],
            allowed_policy_ids=allowed_policy_ids,
            db=db,
        )

    if name == "evaluate_document_policy":
        return evaluate_document_policy(
            document_id=args["document_id"],
            policy_id=args["policy_id"],
            allowed_document_ids=allowed_document_ids,
            allowed_policy_ids=allowed_policy_ids,
            db=db,
        )

    return {"status": "unknown_tool"}
