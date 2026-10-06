SCHEMAS = {
    "cv": """
{
  "name": null,
  "email": null,
  "phone": null,
  "skills": [],
  "education": []
}
""",

    "invoice": """
{
  "invoice_number": null,
  "vendor": null,
  "invoice_date": null,
  "due_date": null,
  "total": null
}
""",

    "receipt": """
{
  "merchant": null,
  "date": null,
  "total": null,
  "payment_method": null
}
""",

    "contract": """
{
  "parties": [],
  "start_date": null,
  "end_date": null,
  "signature_status": null
}
"""
}


FIELD_INSTRUCTIONS = {
    "cv": """
- name: person's full name
- email: email address exactly as written
- phone: phone number exactly as written
- skills: all explicitly mentioned skills
- education: degrees, universities, colleges, or qualifications
""",

    "invoice": """
- invoice_number: invoice identifier
- vendor: company or person issuing the invoice
- invoice_date: date the invoice was issued
- due_date: payment due date
- total: final invoice total including currency if shown
""",

    "receipt": """
- merchant: store/company/business name
- date: transaction date
- total: final amount paid including currency
- payment_method: Visa, Mastercard, cash, etc.
""",

    "contract": """
- parties: all parties involved in the agreement
- start_date: contract start/effective date
- end_date: contract end/expiration date
- signature_status: return "signed" if the document says it was signed,
  "unsigned" if explicitly unsigned, otherwise null
"""
}


def build_extraction_prompt(text: str, document_type: str) -> str:
    if document_type not in SCHEMAS:
        raise ValueError(
            f"Unsupported document type: {document_type}"
        )

    return f"""
You are extracting structured information from a {document_type}.

Read the entire document carefully.

FIELDS TO EXTRACT:
{FIELD_INSTRUCTIONS[document_type]}

OUTPUT FORMAT:
{SCHEMAS[document_type]}

Rules:
- Copy values from the document whenever explicitly present.
- Do not invent information.
- Do not return null when information is clearly present.
- Preserve names, dates, numbers and currencies.
- If a scalar field does not exist, use null.
- If a list has no values, use [].
- Return only valid JSON.
- Do not include Markdown or explanations.

DOCUMENT:
---BEGIN DOCUMENT---
{text}
---END DOCUMENT---
"""