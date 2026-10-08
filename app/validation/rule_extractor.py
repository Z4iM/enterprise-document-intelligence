import json

from app.llm.base import LLMProvider
from app.llm.validator import clean_json_response
from app.validation.rule_schemas import PolicyRule
from app.validation.source_verifier import verify_rule


def extract_policy_rules(
    policy_text: str,
    chunk_id: str,
    provider: LLMProvider
) -> list[PolicyRule]:

    prompt = f"""
You are extracting business rules from a company policy.

POLICY TEXT:
{policy_text}

SOURCE CHUNK ID:
{chunk_id}

Extract explicit numerical threshold rules.

Return only a valid JSON array.

Each rule must contain:
- rule_id
- category
- field
- operator
- threshold
- currency
- action
- approval_role
- source_chunk_id

Allowed operators: >, >=, <, <=, ==
Allowed actions:
requires_approval, requires_documentation, policy_violation

Instructions:
- Extract only rules explicitly supported by the policy.
- Never invent thresholds.
- Use "total" as the field for monetary expense limits.
- Use null for approval_role when no approval is specified.
- Copy the source chunk ID exactly.
- Do not invent a policy section number.
- Return [] if no numerical rule is present.
- source_quote: Copy the exact policy sentence that establishes
the comparison condition and action.
- Do not paraphrase the quote.
- Do not invent evidence.
- If no exact supporting sentence exists, return [].
IMPORTANT RULE EXTRACTION INSTRUCTIONS:

1. Identify the ACTION first.

2. Identify the exact sentence that triggers
   that action.

3. Extract the comparison operator from the
   action-triggering sentence, not from an
   unrelated sentence.

4. "Above", "over", "exceeds", "greater than"
   mean >.

5. "At least", "or more", "minimum"
   mean >=.

6. "Below", "under", "less than"
   mean <.

7. "Up to", "at most", "no more than"
   mean <=.

8. If the policy says "requires manager approval",
   approval_role must be "manager".

9. Never combine the comparison operator from
   one sentence with the action from another.

10. If the action or comparison condition is
    ambiguous, return [] rather than guessing.

Example output:
[
  {{
    "rule_id": "4.1",
    "category": "meal",
    "field": "total",
    "operator": ">",
    "threshold": "100.00",
    "currency": "USD",
    "action": "requires_approval",
    "approval_role": "manager",
    "source_chunk_id": "{chunk_id}"
  }}
]
"""

    raw_response = provider.generate(prompt)

    cleaned = clean_json_response(raw_response)

    parsed = json.loads(cleaned)

    if not isinstance(parsed, list):
        raise ValueError(
            "Expected a JSON array of policy rules."
        )

    rules = [
        PolicyRule.model_validate(item)
        for item in parsed
    ]

    verified_rules = []

    for rule in rules:

        # Confirm the source belongs to this chunk
        if rule.source_chunk_id != chunk_id:
            raise ValueError(
                "Rule references an unexpected source chunk."
            )

        # Verify that the policy supports the rule
        verification = verify_rule(
            rule=rule,
            policy_text=policy_text
        )

        if verification["verified"]:
            verified_rules.append(rule)

        else:
            print(
                f"REJECTED RULE {rule.rule_id}: "
                f"{verification['reason']}"
            )

    return verified_rules