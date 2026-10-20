from app.validation.business_rules import (
    evaluate_expense_rules
)


test_cases = [
    {
        "total": "$15.06",
        "expense_category": "meal"
    },
    {
        "total": "$25",
        "expense_category": "meal"
    },
    {
        "total": "$100",
        "expense_category": "meal"
    },
    {
        "total": "$175",
        "expense_category": "meal"
    }
]


for receipt in test_cases:

    result = evaluate_expense_rules(
        receipt
    )

    print("\n-----------------------------")
    print("Amount:", receipt["total"])
    print("Status:", result["status"])
    print("Summary:", result["summary"])

    for check in result["checks"]:
        print("Check:", check)

    print(
        "Required actions:",
        result["required_actions"]
    )