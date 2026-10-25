from app.llm.http_provider import HTTPModelProvider

provider = HTTPModelProvider()

response = provider.generate(
    """
Return only JSON.

Extract the invoice number.

DOCUMENT:
Invoice Number: INV-7777
"""
)

print(response)