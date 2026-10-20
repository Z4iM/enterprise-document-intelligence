from app.llm.http_provider import HTTPModelProvider
from app.rag.policy_validator import validate_against_policy


provider = HTTPModelProvider()


receipt = {
    "merchant": "Example Restaurant",
    "date": "07/10/2026",
    "total": "$175",
    "payment_method": "Visa",
    "expense_category": "meal"
}

receipt_text = """
Example Restaurant
Date: 07/10/2026
Meal expense
Total: $175
Paid with Visa
"""


result = validate_against_policy(
    document_type="receipt",
    structured_data=receipt,
    document_text=receipt_text,
    provider=provider,
    top_k=3
)


print("\nVALIDATION:")
print(result["validation"])


print("\nRETRIEVED SOURCES:")

for source in result["retrieved_chunks"]:
    print(
        source["chunk_id"],
        round(source["similarity_score"], 4)
    )

    print(source["text"])