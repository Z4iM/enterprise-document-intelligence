from app.validation.rule_evaluator import evaluate_rule
from app.validation.rule_schemas import PolicyRule

rules = [
    PolicyRule(
        rule_id="4.1",
        category="meal",
        field="total",
        operator=">",
        threshold="100.00",
        currency="USD",
        action="requires_approval",
        approval_role="manager",
        source_chunk_id="demo-meal-chunk",
    ),
    PolicyRule(
        rule_id="4.2",
        category="hotel",
        field="total",
        operator=">",
        threshold="220.00",
        currency="USD",
        action="requires_approval",
        approval_role="director",
        source_chunk_id="demo-hotel-chunk",
    ),
    PolicyRule(
        rule_id="4.3",
        category="ground_transportation",
        field="total",
        operator=">",
        threshold="80.00",
        currency="USD",
        action="policy_violation",
        source_chunk_id="demo-transport-chunk",
    ),
]


documents = [
    {
        "expense_category": "meal",
        "total": "$175",
    },
    {
        "expense_category": "hotel",
        "total": "$250",
    },
    {
        "expense_category": "ground_transportation",
        "total": "$90",
    },
    {
        "expense_category": "meal",
        "total": "$15.06",
    },
]


for document in documents:

    print("\nDOCUMENT:", document)

    for rule in rules:

        result = evaluate_rule(
            rule=rule,
            document_data=document,
        )

        if result.applicable:
            print(result.model_dump())