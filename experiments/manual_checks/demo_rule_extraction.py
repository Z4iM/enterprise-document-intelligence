from app.llm.http_provider import HTTPModelProvider
from app.validation.rule_extractor import extract_policy_rules

provider = HTTPModelProvider()

policy_text = """
4.1 Meals

Meal expenses are reimbursable up to $100 per person
per day during approved business travel or authorized
client activity.

Any meal expense above $100 requires manager
approval before reimbursement.
"""

rules = extract_policy_rules(
    policy_text=policy_text,
    chunk_id="test-meals-001",
    provider=provider
)

print("\nEXTRACTED RULES:")

for rule in rules:
    print(
        rule.model_dump_json(indent=2)
    )