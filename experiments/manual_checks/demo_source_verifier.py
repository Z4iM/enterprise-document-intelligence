from app.validation.rule_schemas import PolicyRule
from app.validation.source_verifier import verify_rule

policy_text = """
4.1 Meals
Any meal expense above $100 requires manager approval
before reimbursement.
"""

quote = (
    "Any meal expense above $100 requires manager approval "
    "before reimbursement."
)

base_rule = {
    "rule_id": "4.1",
    "category": "meal",
    "field": "total",
    "threshold": "100.00",
    "currency": "USD",
    "action": "requires_approval",
    "approval_role": "manager",
    "source_chunk_id": "test-meals-001",
    "source_quote": quote
}

wrong_rule = PolicyRule(
    **base_rule,
    operator=">="
)

correct_rule = PolicyRule(
    **base_rule,
    operator=">"
)

missing_quote_rule = PolicyRule(
    **{
        **base_rule,
        "source_quote": None,
        "operator": ">"
    }
)

for name, rule in [
    ("Wrong operator", wrong_rule),
    ("Correct operator", correct_rule),
    ("Missing quote", missing_quote_rule)
]:
    print(
        name,
        verify_rule(rule, policy_text)
    )