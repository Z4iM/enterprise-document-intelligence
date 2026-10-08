
import re
from decimal import Decimal

from app.validation.action_verifier import detect_policy_action
from app.validation.rule_schemas import PolicyRule
from app.validation.scope_verifier import verify_rule_scope


def normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def verify_rule(
    rule: PolicyRule,
    policy_text: str
) -> dict:

    # -----------------------------------------
    # 1. Verify original source evidence
    # -----------------------------------------

    quote = rule.source_quote

    if not quote or not quote.strip():
        return {
            "verified": False,
            "reason": "Missing source quote."
        }

    normalized_quote = normalize_whitespace(quote)
    normalized_policy = normalize_whitespace(policy_text)

    if normalized_quote not in normalized_policy:
        return {
            "verified": False,
            "reason": "Source quote not found in policy."
        }

    text = quote.lower()

    # -----------------------------------------
    # 2. Verify comparison operator
    # -----------------------------------------

    operator_patterns = {
        ">=": r"\b(at least|or more|no less than)\b",
        ">": r"\b(above|over|exceeds|greater than)\b",
        "<=": r"\b(up to|at most|no more than)\b",
        "<": r"\b(below|under|less than)\b",
    }

    detected_operators = [
        operator
        for operator, pattern in operator_patterns.items()
        if re.search(pattern, text)
    ]

    if len(detected_operators) != 1:
        return {
            "verified": False,
            "reason": "Ambiguous or unsupported comparison language."
        }

    detected_operator = detected_operators[0]

    if rule.operator != detected_operator:
        return {
            "verified": False,
            "reason": (
                f"Operator mismatch: policy implies "
                f"{detected_operator}, model extracted {rule.operator}."
            )
        }

    # -----------------------------------------
    # 3. Verify numerical threshold
    # -----------------------------------------

    amounts = re.findall(
        r"\$\s*(\d[\d,]*(?:\.\d+)?)",
        quote
    )

    extracted_amounts = {
        Decimal(value.replace(",", ""))
        for value in amounts
    }

    if rule.threshold not in extracted_amounts:
        return {
            "verified": False,
            "reason": "Threshold not supported by source quote."
        }

    # -----------------------------------------
    # 4. Verify the required action
    # -----------------------------------------

    action_check = detect_policy_action(quote)

    if not action_check["verified"]:
        return {
            "verified": False,
            "reason": action_check["reason"]
        }

    if rule.action != action_check["action"]:
        return {
            "verified": False,
            "reason": (
                f"Action mismatch: policy requires "
                f"{action_check['action']}, "
                f"model extracted {rule.action}."
            )
        }

    # -----------------------------------------
    # 5. Verify approval role if required
    # -----------------------------------------

    if rule.action == "requires_approval":

        role = rule.approval_role

        if not role or role.lower() not in text:
            return {
                "verified": False,
                "reason": "Approval role not supported by source quote."
            }

        if not re.search(
            r"\bapprov(?:al|e|ed|es|ing)\b",
            text
        ):
            return {
                "verified": False,
                "reason": "Approval requirement not found in evidence."
            }

    elif rule.approval_role is not None:
        return {
            "verified": False,
            "reason": (
                "Approval role supplied for a rule "
                "that does not require approval."
            )
        }

    # -----------------------------------------
    # 6. Verify category / policy scope
    # -----------------------------------------

    scope_check = verify_rule_scope(
        source_quote=quote,
        extracted_category=rule.category
    )

    if not scope_check["verified"]:
        return {
            "verified": False,
            "reason": scope_check["reason"]
        }

    # -----------------------------------------
    # 7. All verification checks passed
    # -----------------------------------------

    return {
        "verified": True,
        "reason": "Rule matches the supplied source evidence."
    }
