# Cooperating specialists — milestone 5

[NEXUS EDI](../README.md) · [Documentation guide](README.md)

The existing three-tool investigator remains available. This adds a separate queued,
development-only LangGraph workflow. Official results remain deterministic.

## Architecture and authority

1. Authenticated intake resolves the selected document/policy. Organization/account/
   request keys make retries idempotent; changed payloads conflict.
2. Shared document eligibility runs first. The document specialist independently uses
   only `inspect_document`. Reviewed type/category/total provide bounded server-derived
   context to the policy specialist.
3. The policy specialist independently chooses `get_policy_evidence` or
   `search_policy_sources`. It cannot inspect documents, approve rules or decide expenses.
   Search returns untrusted candidates, never activated rules.
4. The coordinator reloads **all** current, source-verified, human-approved rules and
   reviewed fields for deterministic evaluation. Models return constrained
   `ready`/`needs_review`/`abstain` signals; they cannot trim the evaluated rule set.
5. Actual LangGraph interrupts wait for review. Resume reloads canonical records; a
   request/model signal cannot supply approval. Every node/tool rechecks active account,
   organization, ownership and role. Existing session/CSRF/local/token guards remain.

The shared adapter implements bounded manual tool loops. Roles have separate tool
declarations, prompts, conversations and decisions. No new dependency or service.
Disabled/unavailable Gemini produces an explicitly labeled deterministic fallback;
invalid tools/arguments or decision payloads block the model path.

## Persistence and resource bounds

Workflow metadata lives in SQLite/PostgreSQL; graph state lives in
`EDI_DATA_ROOT/specialist_checkpoints.sqlite`. Each lease forks the published checkpoint
and pending interrupts into its own thread. Only the queue's unexpired-lease transaction
publishes a new pointer with business results. Stale attempts leave unpublished orphans.
Missing canonical files/threads fail closed. Back up the business DB, originals **and
both checkpoint files together**. Import requires referenced specialist checkpoints.

Bounds: three model turns/two tools per role; eight model calls across published state;
one provider retry; 15-second request timeout; 90-second cooperative execution deadline;
existing 180-second lease/three attempts; eight resumes; 64 trace events; bounded payloads.
Deadlines are not process-kill guarantees. Crashes can repeat billable calls before
publication: inference is at least once. Orphan retention remains operational work.

## Documentation requirements

An explicit receipt/invoice requirement names an evidence type, not an automatically
missing file. The original uploaded receipt can qualify after Reviewer/Admin inspection
of its original and reviewed fields. Other supporting files must be reviewed and have
the same uploader/organization. Employees see the checklist but cannot attest.
Generic “supporting documentation” remains `needs_clarification`; no invented proof type.
Attestation is human inspection, not automatic transaction matching or expense approval.

Source rule, target provenance/fields and supporting evidence fingerprints bind each
confirmation. Changed inputs/revoked reviewer access make it stale. Reviews are
append-only; exact retries do not duplicate them. Historical rows/audit events remain.

## Local demo and migration

Back up first; apply `python -m alembic upgrade head` to the same DB/root used by API and
worker. Current head: `20261031_observability` (M6 includes the specialist migration). Development did not migrate real user data.
Ambiguous historical approvals can now fail source-semantic revalidation and need
review; existing records are not silently rewritten.

| Backend / worker | Next.js server (`npm run dev`) |
|---|---|
| `EDI_ENABLE_DEV_WORKFLOWS=true` | `EDI_ENABLE_DEV_WORKFLOWS_FRONTEND=true` |
| Private `EDI_DEV_WORKFLOW_TOKEN` | Same private token |
| Optional existing Gemini configuration | No browser provider key |

Open `http://127.0.0.1:3000/workflows`. Optional private
`EDI_DEV_WORKFLOW_ORIGIN=http://127.0.0.1:<port>` supports isolated alternate ports;
only explicit loopback HTTP origins are accepted. Never use `NEXT_PUBLIC_*` for tokens.
Production builds keep controls unavailable and gateway 404; no deployment authorized.
No-provider mode demonstrates the same review lifecycle with clearly labeled fallback.
Live Gemini calls need separate approval.

Upload/review an Arabic policy, approve supported verified rules, upload an Arabic
receipt and start a workflow. Correct fields as Reviewer, confirm any explicit receipt
requirement, then resume as employee. Inspect both role traces, original Arabic quotes
and deterministic approval requirements. An approval requirement is not an approval.

## Measurements and limitations

The fixed development corpus has 40 synthetic templates: 20/language across receipts,
invoices and policies, including four scans/language. All 40 source texts are reference
baselines; eight are additionally rendered and run through actual application OCR.

| Measurement | English | Arabic |
|---|---:|---:|
| Reference native fields / supported policy cases | 100% / 100% | 100% / 100% |
| Scanned field exact accuracy (4 scans/language) | 75% | 50% |
| Scanned nonempty precision / false abstention | 75% / 0% | 88.89% / 43.75% |
| OCR character / word error rate | 0.0091 / 0.0662 | 0.4103 / 0.4033 |
| Scanned policy verification decision (one case/language) | 1/1 | 0/1 |

These are small template regressions, **not general Arabic accuracy**. Arabic OCR needs
substantial improvement. Ambiguous dates/money/currencies and unsupported grammar stay
review-gated. Original Unicode quotes remain unchanged; normalization serves comparisons.
Arabic verification supports narrow explicit comparisons/categories/actions/roles, not
unrestricted policy interpretation. Held-out scans, PDF tables and real-model quality
remain release work. [Raw measurements](benchmarks/bilingual-v1.json).

The [single-agent comparison](benchmarks/specialists-control-v1.json) uses scripted
generation on 12 fixed bilingual scenarios. Both paths achieved 12/12 canonical outcomes;
specialists used 50 scripted model calls versus 34. This demonstrates control and role
separation with extra overhead, **not a generative-quality gain**. Real tokens/cost and
provider latency are unmeasured, not zero. A live benchmark needs separate authorization.

```powershell
.\.venv\Scripts\python.exe evals/bilingual/run.py --check-native --output .local/bilingual.json
.\.venv\Scripts\python.exe evals/specialists/run.py --output .local/specialists.json
# Actual OCR: add --docker <executable> --image <built-backend> --font <public-Arabic-font>
```

CI runs native goldens and scripted control comparisons without model inference, plus
production gateway tests and a separate development Arabic browser journey. Only
generation is mocked in that journey; authentication, worker, review, checkpoints and
evaluation are real. Container verification includes pause/restart/review/resume.
See [observed verification](VERIFICATION.md). Milestone 6 adds telemetry and broader gates.
