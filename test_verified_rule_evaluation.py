from app.llm.http_provider import HTTPModelProvider
from app.validation.two_stage_extractor import extract_verified_rules
from app.validation.rule_schemas import PolicyRule
from app.validation.rule_evaluator import evaluate_rule


provider = HTTPModelProvider()

policy_text = """
4.1 Meals

Any meal expense above $100 requires manager approval
before reimbursement.
"""

result = extract_verified_rules(
    policy_text=policy_text,
    chunk_id="test-meals-001",
    provider=provider
)

print("\nEXTRACTION STATUS:", result["status"])

if result["status"] == "verified":

    rule = PolicyRule.model_validate(
        result["verified_rules"][0]
    )

    for amount in ["$15.06", "$100", "$175"]:

        document = {
            "expense_category": "meal",
            "total": amount
        }

        evaluation = evaluate_rule(
            rule=rule,
            document_data=document
        )

        print(
            amount,
            "→",
            evaluation.status,
            "| Applicable:",
            evaluation.applicable
        )

else:
    print("Rule extraction was not verified.")
    print(result["rejected_rules"])