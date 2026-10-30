import re


def detect_policy_action(
    source_quote: str
) -> dict:

    text = " ".join(
        source_quote.lower().split()
    )

    approval_pattern = (
        r"\b(?:requires?|needs?|must obtain)\s+"
        r"(?:\w+\s+){0,3}approval\b"
    )

    documentation_pattern = (
        r"\b(?:receipts?|invoices?|documentation|"
        r"supporting documents?)\s+"
        r"(?:is|are)\s+required\b"
    )

    has_approval = bool(
        re.search(approval_pattern, text)
    )

    has_documentation = bool(
        re.search(documentation_pattern, text)
        or re.search(r"\brequires?\s+(?:an?\s+)?(?:receipts?|invoices?|documentation|supporting documents?)\b", text)
    )

    if has_approval and has_documentation:
        return {
            "action": None,
            "verified": False,
            "reason": "Multiple actions detected."
        }

    if has_approval:
        return {
            "action": "requires_approval",
            "verified": True,
            "reason": "Explicit approval requirement."
        }

    if has_documentation:
        return {
            "action": "requires_documentation",
            "verified": True,
            "reason": "Explicit documentation requirement."
        }

    return {
        "action": None,
        "verified": False,
        "reason": "Unsupported action wording."
    }
