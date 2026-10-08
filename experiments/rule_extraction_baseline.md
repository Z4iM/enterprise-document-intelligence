# Policy Rule Extraction — Baseline

Model: Qwen2.5-1.5B-Instruct

## Test policy
Any meal expense above $100 requires manager approval
before reimbursement.

## Expected
- Operator: >
- Threshold: 100
- Category: meal
- Approval role: manager

## With example
- Operator: <=
- Category: meal
- Approval role: null

## Without example
- Operator: >=
- Category: expense_limit
- Approval role: manager

## Finding
The model failed to extract the correct comparison operator
in both runs. Prompt examples affected the generated fields.

## Next
Compare against larger models and verify extracted
rules against source evidence before activating them.