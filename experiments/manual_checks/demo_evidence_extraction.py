from app.llm.http_provider import HTTPModelProvider

provider = HTTPModelProvider()

policy_text = """
4.1 Meals

Meal expenses are reimbursable up to $100 per person
per day during approved business travel or authorized
client activity.

Any meal expense above $100 requires manager
approval before reimbursement.
"""

prompt = f"""
You are an evidence extraction assistant.

POLICY:
{policy_text}

TASK:
Find the exact policy statement that explains
WHEN manager approval is required.

Return only the matching statement.
Do not summarize.
Do not explain.
Do not return JSON.
Do not invent text.

You may combine line breaks into spaces,
but preserve the original wording.
"""

result = provider.generate(prompt)

print("\nEXTRACTED EVIDENCE:")
print(result)