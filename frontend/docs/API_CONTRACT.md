# Frontend / FastAPI contract

[NEXUS EDI](../../README.md) · [Documentation guide](../../docs/README.md)

All business requests require FastAPI session identity. The bridge is allowlisted and
forwards only session cookies, CSRF/origin metadata and content type. It returns server
Set-Cookie headers intact; cache is disabled. Its bounded stream reader rejects oversized
bodies even without Content-Length. Direct backend routes enforce the same authority.

| Feature | Method / path | Authorization |
|---|---|---|
| Login challenge | GET `/auth/csrf` | Public, origin/rate checked; returns CSRF token and HttpOnly session |
| Login | POST `/auth/login` | Pre-login cookie + CSRF; `{email,password}` |
| Current account / logout | GET `/auth/me`, POST `/auth/logout` | Session; writes require CSRF |
| Profile | GET/POST `/auth/profile` | Session; POST `{display_name}` is admin-only; GET user plus server-computed role-specific stats |
| Change password | POST `/auth/change-password` | Session + CSRF + current password; `{current_password,new_password}`; rotates credential and revokes old sessions |
| Documents/upload | GET `/documents`, POST `/documents/upload` | Scoped list; upload ownership from session |
| Detail/original/audit/reviews | GET `/documents/{id}` and suffixes | Own document or organization staff |
| Processing status | GET `/documents/{id}/processing`, `/policies/{id}/processing` | Same scoped resource access; state/attempts/redacted error |
| Retry failed processing | POST `/documents/{id}/processing/retry`, `/policies/{id}/processing/retry` | Document access or policy staff; CSRF; terminal failure only |
| Pending/record review | GET `/reviews/pending`, POST `/documents/{id}/review` | Reviewer/Admin; submitted reviewer name is ignored |
| Approved-rule evaluation | POST `/documents/{id}/validate-approved-policy` | Scoped document and body-selected policy; explicit valid review |
| Policies/upload/original | GET `/policies`, POST `/policies/upload`, GET `/policies/{id}/original` | Organization reads; staff writes |
| Rules | GET `/policies/{id}/rules` | Organization policy |
| Candidate extraction | POST `/policies/{id}/rules/extract-candidates` | Staff; `{chunk_index}`; configured model only |
| Whole-policy extraction | POST `/policies/{id}/rules/extract-all` | Staff; also runs automatically after upload; persisted status returned by GET rules |
| Bulk approval | POST `/policies/{id}/rules/approve-all` | Staff + CSRF; `{rule_ids:[...]}` for 1–100 explicit IDs; all-or-nothing source revalidation and per-rule history |
| Rule decision | POST `/policies/{id}/rules/{rule}/decision` | Staff + verified source + pending state; `{decision,notes?}` |
| Accounts | GET/POST `/admin/users`, POST `/admin/users/{id}/status` | Admin in organization; `{active}` for status |
| Account name | POST `/admin/users/{id}/profile` | Admin in same organization; `{display_name}` only |

Unsafe requests use `x-csrf-token`; the client gets a current token from `/auth/csrf`
before mutation. Missing/expired identity gives 401, denied capability/CSRF gives 403,
out-of-scope/missing IDs give 404, invalid review/decision state gives 409 and invalid
request fields give a sanitized 422. Failed reviews do not write review/audit mutations.

`ValidationResult.validation.required_actions` is an array of objects with `rule_id`,
`action`, `explanation`; the UI renders action labels, not stringifies objects.
`GET /reviews/pending` includes completed needs_review and auto_accepted records. Fallback needs a
validated non-empty correction; it remains regex_fallback in provenance. No review
or rule approval is reimbursement approval. Legacy `/validate-policy` is retired (410)
and not forwarded by the bridge.

The separate `/api/agent/investigate` gateway retains development/loopback/Origin guards,
server-only token and production 404. It additionally forwards the authenticated session
and CSRF; browser JSON supplies a question and optionally a paired `document_id`/`policy_id`
selection. Each ID must be currently accessible to the session; selections only narrow
server-derived DB permissions and never grant access. Unknown grant/role/model fields
remain forbidden. Legacy ID environment settings are ignored. Workflow APIs retain local/token
checks and verify run ownership/linked resources; the specialist dashboard supports guarded execution, review checkpoints and resume.

Browser regression tests exercise login/upload/review/approval/source-download/evidence/
logout plus local account administration. See root docs/VERIFICATION.md for observed
results. Public deployment and general live Gemini quality/cost are not claimed. Both container profiles have dated local recovery evidence in the verification log.

User responses include `display_name` (existing accounts initially have an empty name).
Account creation accepts `display_name`; name updates are admin-only, including self-profile updates, and require a nonblank name of
at most 100 characters. The UI renders names, while `reviewer`/`approved_by` retain stable
IDs and additive `reviewer_name`/`approved_by_name` fields supply scoped labels. Audit
responses include `actor_name`; known legacy human-review ID suffixes are resolved at read
time. Names are current account labels, not immutable historical snapshots.

Default embedded/external mode uploads return HTTP 202 with `job_id`; originals and
resources are saved atomically with the queue job before returning. Inline mode retains
the synchronous component contract. Processing state is queued/running/retry_wait/
completed/failed; completion is not human approval. The UI polls active jobs and refreshes
detail/rules on completion. `/health` is liveness and `/ready` checks DB/migration head.

Policy upload also returns `rule_extraction:{status,message}`. GET rules includes
`extraction_status` and `extraction_message`. `failed` extraction is a saved upload,
not successful AI processing; retry uses the configured model. `completed` describes
processing, not completeness of the model's understanding or full policy coverage.
