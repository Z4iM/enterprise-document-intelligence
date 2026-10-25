import json

from app.llm.http_provider import HTTPModelProvider
from app.validation.two_stage_extractor import extract_verified_rules

provider = HTTPModelProvider()


policy_text = """
4.1 Meals

Meal expenses are reimbursable up to $100 per person
per day during approved business travel or authorized
client activity.

Any meal expense above $100 requires manager
approval before reimbursement.
"""


result = extract_verified_rules(
    policy_text=policy_text,
    chunk_id="test-meals-001",
    provider=provider
)


print("\nPIPELINE STATUS:")
print(result["status"])

print("\nEXTRACTED EVIDENCE:")
print(result["evidence"])

print("\nVERIFIED RULES:")
print(
    json.dumps(
        result["verified_rules"],
        indent=2
    )
)

print("\nREJECTED RULES:")
print(
    json.dumps(
        result["rejected_rules"],
        indent=2
    )
)