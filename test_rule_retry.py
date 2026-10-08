from app.llm.http_provider import HTTPModelProvider
from app.validation.rule_retry import retry_rule_extraction
from app.validation.rule_schemas import PolicyRule
from app.validation.source_verifier import verify_rule

provider = HTTPModelProvider()

evidence = (
    "Receipts are required for individual expenses "
    "of $25 or more."
)

rejected_rule = {
    "rule_id": "RECEIPT-001",
    "category": "individual expenses",
    "field": "total",
    "operator": ">",
    "threshold": "25.00",
    "currency": "USD",
    "action": "requires_approval",
    "approval_role": None,
    "source_quote": evidence,
    "source_chunk_id": "RECEIPT-001",
}

response = retry_rule_extraction(
    provider=provider,
    source_evidence=evidence,
    rejected_rule=rejected_rule,
    rejection_reason=(
        "Operator mismatch: policy implies >=, "
        "model extracted >. "
        "Receipt documentation is required, "
        "not manager approval."
    ),
)

print("\nMODEL RETRY RESPONSE:")
print(response)

try:
    # If your provider returns fenced JSON, we'll improve parsing later.
    import json

    data = json.loads(response)

    # Do not allow the model to alter source provenance.
    data["source_quote"] = evidence
    data["source_chunk_id"] = "RECEIPT-001"

    rule = PolicyRule.model_validate(data)

    result = verify_rule(rule, evidence)

    print("\nREVISED RULE:")
    print(rule.model_dump_json(indent=2))

    print("\nVERIFICATION RESULT:")
    print(result)

except Exception as exc:
    print("\nRETRY FAILED:")
    print(type(exc).__name__, str(exc))