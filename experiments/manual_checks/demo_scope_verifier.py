from app.validation.scope_verifier import verify_rule_scope

cases = [
    (
        "Any meal expense above $100 requires manager approval.",
        "meal",
        True,
    ),
    (
        "A room rate above $220 per night requires director approval.",
        "hotel",
        True,
    ),
    (
        "A receipt is required for any ground-transport expense above $25.",
        "ground_transportation",
        True,
    ),
    (
        "Receipts are required for individual expenses of $25 or more.",
        "purchase",
        False,
    ),
    (
        "Receipts are required for individual expenses of $25 or more.",
        "all_expenses",
        True,
    ),
    (
        "Purchases above $10,000 require director approval.",
        "purchase",
        True,
    ),
]


for text, category, expected in cases:

    result = verify_rule_scope(
        source_quote=text,
        extracted_category=category,
    )

    print(
        category,
        "| Verified:",
        result["verified"],
        "| Expected:",
        result["expected_scope"],
    )

    assert result["verified"] == expected


print("\nAll scope verification tests passed.")