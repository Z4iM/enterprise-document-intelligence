
from google.genai import types


def build_gemini_tools() -> list[types.Tool]:
    """
    Describe EDI's permitted tools to Gemini.

    These are declarations only.
    No database queries or tool executions happen here.
    """

    inspect_document = types.FunctionDeclaration(
        name="inspect_document",
        description=(
            "Inspect a stored enterprise document and retrieve "
            "its reviewed structured extraction data."
        ),
        parameters_json_schema={
            "type": "object",
            "properties": {
                "document_id": {
                    "type": "string",
                    "description": "The document ID to inspect.",
                },
            },
            "required": ["document_id"],
            "additionalProperties": False,
        },
    )

    get_policy_evidence = types.FunctionDeclaration(
        name="get_policy_evidence",
        description=(
            "Retrieve verified, human-approved policy rules "
            "with their supporting source quotes."
        ),
        parameters_json_schema={
            "type": "object",
            "properties": {
                "policy_id": {
                    "type": "string",
                    "description": "The policy ID to inspect.",
                },
            },
            "required": ["policy_id"],
            "additionalProperties": False,
        },
    )

    evaluate_document_policy = types.FunctionDeclaration(
        name="evaluate_document_policy",
        description=(
            "Evaluate a reviewed document against verified, "
            "human-approved policy rules using a deterministic "
            "Python evaluator. Does not approve expenses."
        ),
        parameters_json_schema={
            "type": "object",
            "properties": {
                "document_id": {
                    "type": "string",
                },
                "policy_id": {
                    "type": "string",
                },
            },
            "required": ["document_id", "policy_id"],
            "additionalProperties": False,
        },
    )

    return [
        types.Tool(
            function_declarations=[
                inspect_document,
                get_policy_evidence,
                evaluate_document_policy,
            ]
        )
    ]
