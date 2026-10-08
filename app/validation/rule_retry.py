import json

from app.llm.base import LLMProvider


def retry_rule_extraction(
    provider: LLMProvider,
    source_evidence: str,
    rejected_rule: dict,
    rejection_reason: str,
) -> str:
    """
    Ask the model to revise an incorrectly extracted rule.

    Returns the raw model response.
    The caller MUST validate and verify the revised rule.
    """

    prompt = f"""
You extract structured business rules from company policies.

An earlier extraction was REJECTED because it contradicted
the original policy evidence.

ORIGINAL POLICY EVIDENCE:
{source_evidence}

REJECTED JSON:
{json.dumps(rejected_rule, indent=2)}

VERIFICATION ERROR:
{rejection_reason}

TASK:
Correct the extracted JSON using ONLY the original evidence.

Important rules:
- "above $100" means operator ">"
- "over $100" means operator ">"
- "$100 or more" means operator ">="
- "at least $100" means operator ">="
- "up to $100" means operator "<="
- "below $100" means operator "<"

ACTION RULES:
- Manager or director approval -> requires_approval
- Receipt or documentation required -> requires_documentation
- Explicit prohibition -> policy_violation
- Do not invent an approval requirement.

Keep the original source_chunk_id.
Keep source_quote identical to the original evidence.
Return exactly ONE JSON object.
Do not include Markdown or explanations.

CATEGORY AND SCOPE RULES:
- Meal or restaurant expense -> meal
- Hotel or room rate -> hotel
- Taxi, rideshare, or ground transport -> ground_transportation
- Purchases or procurement -> purchase
- General rules covering individual expenses -> all_expenses
- Never classify a general receipt requirement as purchase.
- Do not invent a narrower category than the source supports.
- When correcting a scope mismatch, use the expected scope stated in the verification error.
"""

    return provider.generate(prompt).strip()