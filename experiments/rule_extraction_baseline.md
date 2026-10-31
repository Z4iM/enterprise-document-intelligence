# Policy Rule Extraction — Baseline

[NEXUS EDI](../README.md) · [Documentation guide](../docs/README.md)

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

## Interpretation and current implementation
This historical two-run experiment is not a model-quality benchmark. The application now verifies proposed rules against source evidence and requires explicit human approval before activation. Broader model comparisons remain unmeasured; see [current specialist evidence](../docs/SPECIALISTS.md).
