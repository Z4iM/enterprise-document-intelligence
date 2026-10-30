import re

from app.validation.category_normalizer import normalize_category


def verify_rule_scope(
    source_quote: str,
    extracted_category: str,
) -> dict:
    """
    Verify a rule's category against explicit source wording.

    Conservative prototype:
    - Recognizes known specific categories.
    - Recognizes explicit general expense language.
    - Rejects unsupported or ambiguous scope.
    """

    text = " ".join(source_quote.lower().split())

    # Match explicit general expense language.
    general_patterns = [
        r"\bindividual expenses\b",
        r"\ball expenses\b",
        r"\bevery expense\b",
        r"\bany expense\b",
        r"^expenses of\s+\$?\s*\d",
    ]

    expected_scope = None

    if any(re.search(pattern, text) for pattern in general_patterns):
        expected_scope = "all_expenses"

    else:
        # Check specific categories.
        # Use longer / more distinctive patterns where possible.
        category_patterns = {
            "ground_transportation": [
                r"\bground.transport\b",
                r"\btaxi\b",
                r"\brideshare\b",
            ],
            "hotel": [
                r"\bhotels?\b",
                r"\broom rate\b",
                r"\blodging\b",
            ],
            "meal": [
                r"\bmeals?\b",
                r"\brestaurant\b",
            ],
            "purchase": [
                r"\bpurchases?\b",
                r"\bpurchasing\b",
                r"\bprocurement\b",
            ],
        }

        matches = [
            category
            for category, patterns in category_patterns.items()
            if any(re.search(pattern, text) for pattern in patterns)
        ]

        if len(matches) == 1:
            expected_scope = matches[0]

    if expected_scope is None:
        return {
            "verified": False,
            "reason": "Cannot determine rule scope from evidence.",
            "expected_scope": None,
        }

    actual_scope = normalize_category(extracted_category)

    if actual_scope != expected_scope:
        return {
            "verified": False,
            "reason": (
                f"Scope mismatch: source implies "
                f"{expected_scope}, model extracted {actual_scope}."
            ),
            "expected_scope": expected_scope,
        }

    return {
        "verified": True,
        "reason": "Rule scope matches source evidence.",
        "expected_scope": expected_scope,
    }
