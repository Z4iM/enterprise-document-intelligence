import json

from app.llm.base import LLMProvider
from app.rag.retriever import retrieve_policy_context
from app.llm.validator import clean_json_response
from decimal import Decimal
from app.validation.business_rules import parse_money


def validate_against_policy(
    document_type: str,
    structured_data: dict,
    document_text: str,
    provider: LLMProvider,
    top_k: int = 3
) -> dict:

    # -------------------------------------------------
    # 1. Build retrieval query
    # -------------------------------------------------

    expense_category = structured_data.get(
        "expense_category"
    )

    total = structured_data.get(
        "total"
    )

    merchant = structured_data.get(
        "merchant"
    )

    # Focused query for expense-related documents
    if expense_category:

        query = f"""
Company policy for {expense_category} expenses.

Expense category: {expense_category}
Amount: {total}
Merchant: {merchant}

What approval, reimbursement limit, receipt requirement,
or restriction applies to this expense?
"""

    # Generic fallback for other document types
    else:

        query = f"""
Find company policies relevant to this document.

Document type:
{document_type}

Structured information:
{json.dumps(structured_data, indent=2)}

Original document text:
{document_text}
"""

    # -------------------------------------------------
    # 2. Retrieve relevant policy chunks
    # -------------------------------------------------

    retrieved_chunks = retrieve_policy_context(
        query=query,
        top_k=top_k
    )

    # -------------------------------------------------
    # 3. Print raw results for debugging
    # -------------------------------------------------

    print("\nRAW RETRIEVAL RESULTS:")

    for chunk in retrieved_chunks:

        print(
            "\nScore:",
            round(
                chunk["similarity_score"],
                4
            )
        )

        print(
            chunk["text"][:300]
        )

    # -------------------------------------------------
    # 4. Dynamic relevance filtering
    # -------------------------------------------------

    MIN_SIMILARITY = 0.40
    SCORE_MARGIN = 0.12

    if retrieved_chunks:

        best_score = retrieved_chunks[0][
            "similarity_score"
        ]

        dynamic_threshold = max(
            MIN_SIMILARITY,
            best_score - SCORE_MARGIN
        )

        print(
            "\nDynamic threshold:",
            round(
                dynamic_threshold,
                4
            )
        )

        retrieved_chunks = [
            chunk
            for chunk in retrieved_chunks
            if chunk["similarity_score"]
            >= dynamic_threshold
        ]

    # -------------------------------------------------
    # 5. Stop if no strong policy evidence exists
    # -------------------------------------------------

    if not retrieved_chunks:

        return {
            "validation": {
                "status": "needs_review",
                "summary": (
                    "No sufficiently relevant company "
                    "policy was retrieved."
                ),
                "violations": [],
                "required_actions": [],
                "source_chunk_ids": []
            },
            "retrieved_chunks": []
        }

    # -------------------------------------------------
    # 6. Build policy context
    # -------------------------------------------------

    policy_context_parts = []

    for result in retrieved_chunks:

        policy_context_parts.append(
            f"""
CHUNK ID: {result["chunk_id"]}

POLICY TEXT:
{result["text"]}
"""
        )

    policy_context = "\n".join(
        policy_context_parts
    )

    # -------------------------------------------------
    # 7. Build augmented RAG prompt
    # -------------------------------------------------

    prompt = f"""
You are validating a company document against
company policies.

DOCUMENT TYPE:
{document_type}

STRUCTURED DOCUMENT DATA:
{json.dumps(structured_data, indent=2)}

ORIGINAL DOCUMENT TEXT:
{document_text}

RETRIEVED COMPANY POLICY:
{policy_context}

Determine whether the document complies with the
retrieved company policy.

Return only valid JSON using exactly this structure:

{{
  "status": "compliant | requires_approval | policy_violation | needs_review",
  "summary": null,
  "violations": [],
  "required_actions": [],
  "source_chunk_ids": []
}}

Rules:

- Use only the retrieved policy text.
- Never invent company requirements.

- Use "compliant" only when the document clearly
satisfies the relevant policy with no additional
approval or action required.

- Use "requires_approval" when the document exceeds
a normal threshold but the policy explicitly allows
it with approval.

- Use "policy_violation" when the policy explicitly
prohibits the action or when a required condition
has already been violated.

- Use "needs_review" only when the retrieved policy
does not contain enough information to decide.

- Compare monetary values numerically.

- If the document amount is greater than a policy
threshold, do not return "compliant".

- Only include required actions explicitly stated
by the retrieved policy.

- Include only chunk IDs actually used to make
the decision.

- Do not create extra fields outside the required
JSON structure.
"""

    # -------------------------------------------------
    # 8. Send prompt to Qwen
    # -------------------------------------------------

    raw_response = provider.generate(
        prompt
    )

    # -------------------------------------------------
    # 9. Clean JSON response
    # -------------------------------------------------

    cleaned_response = clean_json_response(
        raw_response
    )

    result = json.loads(
        cleaned_response
    )
    # ------------------------------------------
    # Deterministic business-rule validation
    # ------------------------------------------

    category = str(
        structured_data.get("expense_category") or ""
    ).strip().lower()

    # Only apply our current hardcoded rules when
    # validating a receipt against the matching
    # Northstar Analytics employee policy.

    NORTHSTAR_POLICY_ID = (
        "153b2620-111d-473e-991d-94b4734024b2"
    )

    has_matching_policy = any(
        chunk.get("policy_id") == NORTHSTAR_POLICY_ID
        for chunk in retrieved_chunks
    )

    has_meal_policy = any(
        chunk.get("policy_id") == NORTHSTAR_POLICY_ID
        and chunk.get("text", "").lstrip().startswith("4.1 Meals")
        for chunk in retrieved_chunks
    )

    if (
        document_type == "receipt"
        and category == "meal"
        and has_matching_policy
        and has_meal_policy
    ):
        rules_result = evaluate_expense_rules(
            structured_data
        )

        # For our supported meal-limit rule, Python
        # is authoritative over Qwen's decision.
        result["status"] = rules_result["status"]
        result["summary"] = rules_result["summary"]
        result["violations"] = rules_result["violations"]
        result["required_actions"] = rules_result["required_actions"]

        # Retain only citations supporting this decision.
        result["source_chunk_ids"] = [
            chunk["chunk_id"]
            for chunk in retrieved_chunks
            if (
                chunk.get("policy_id") == NORTHSTAR_POLICY_ID
                and chunk.get("text", "").lstrip().startswith("4.1 Meals")
            )
        ]

        result["deterministic_checks"] = rules_result["checks"]

    # -------------------------------------------------
    # 10. Return validation + evidence
    # -------------------------------------------------
    # -------------------------------------------------
    # 10. Apply deterministic consistency guardrails
    # -------------------------------------------------

    # Deterministic verification for policy section 4.4
    NORTHSTAR_POLICY_ID = (
        "153b2620-111d-473e-991d-94b4734024b2"
    )

    receipt_policy_chunks = [
        chunk for chunk in retrieved_chunks
        if (
            chunk.get("policy_id") == NORTHSTAR_POLICY_ID
            and chunk.get("text", "").lstrip().startswith(
                "4.4 Receipts and Missing Documentation"
            )
        )
    ]

    if document_type == "receipt" and receipt_policy_chunks:

        amount = parse_money(structured_data.get("total"))

        if amount is not None:

            receipt_required = amount >= Decimal("25.00")

            result["status"] = (
                "needs_review" if receipt_required
                else "compliant"
            )

            result["violations"] = []
            result["required_actions"] = []

            result["summary"] = (
                "Receipt documentation is required; "
                "documentation availability has not been verified."
                if receipt_required
                else
                "The expense is below the $25 receipt "
                "documentation threshold."
            )

            result["deterministic_checks"] = [{
                "rule": "4.4 Receipts and Missing Documentation",
                "amount": str(amount),
                "threshold": "25.00",
                "receipt_required": receipt_required
            }]

            result["source_chunk_ids"] = [
                chunk["chunk_id"]
                for chunk in receipt_policy_chunks
            ]
    violations = result.get(
        "violations",
        []
    )

    required_actions = result.get(
        "required_actions",
        []
    )

    status = result.get(
        "status"
    )


    # A document cannot be compliant if the model
    # already identified a violation.
    if violations and status == "compliant":

        result["status"] = "policy_violation"


    # A document cannot be fully compliant if an
    # additional approval/action is still required.
    elif (
        required_actions
        and status == "compliant"
    ):

        result["status"] = "requires_approval"
    return {
        "validation": result,
        "retrieved_chunks": retrieved_chunks
    }
