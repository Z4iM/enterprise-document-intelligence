from app.validation.action_verifier import (
    detect_policy_action
)


cases = [
    (
        "Any meal expense above $100 requires "
        "manager approval before reimbursement.",
        "requires_approval"
    ),
    (
        "A receipt is required for any ground-transport "
        "expense above $25.",
        "requires_documentation"
    ),
    (
        "Receipts are required for individual expenses "
        "of $25 or more.",
        "requires_documentation"
    )
]


for text, expected in cases:

    result = detect_policy_action(text)

    print("\nEvidence:", text)
    print("Expected:", expected)
    print("Detected:", result["action"])
    print("Verified:", result["verified"])

    assert result["action"] == expected
    assert result["verified"] is True


print("\nAll action verification tests passed.")