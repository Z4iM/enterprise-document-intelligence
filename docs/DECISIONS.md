# Engineering decisions

## ADR 001 — Shared document eligibility (accepted, 2026-10-30)

**Problem:** API evaluation accepted unreviewed/rejected records while agent and
workflow gates disagreed; corrected fallback records could never proceed.

**Decision:** All three use one pure eligibility function. Require completed processing,
explicit review and schema-valid non-empty fields. Fallback needs a human correction;
review snapshots persist atomically and original extraction provenance is retained.
Auto-accepted classification is not explicit review. Surface it in the review queue.

**Trade-off:** More review is required. Existing automatically accepted records and
invalid/unknown-schema records must be reviewed/corrected before evaluation. No schema
migration or retroactive data rewriting is performed. Authentication remains separate.

## ADR 002 — Retire model-led official evaluation (accepted, 2026-10-30)

**Decision:** The legacy `validate-policy` endpoint returns 410 with a migration pointer.
The verified approved-rule endpoint remains the official API. Experimental RAG code is
retained for future measured comparison, not exposed as a second authority.

**Trade-off:** Callers of the legacy endpoint must migrate. Keeping two inconsistent
decision contracts was unsafe. Reverting the code is possible, but restoring the old
official behavior would also restore the identified trust defect.

## ADR 003 — Preserve stack and minimize services (accepted)

Keep FastAPI, Next.js, Gemini tools and LangGraph. Add database sessions with Argon2,
scoped RBAC, PostgreSQL/Alembic, then pgvector/full-text retrieval and a small durable
worker. Avoid a new identity service, Redis or reranker until requirements justify them.
Opaque sessions permit logout/revocation but require carefully tested lifecycle/CSRF
logic. OIDC remains the production SSO direction. No dependencies added in milestone 1.

## ADR 004 — Isolate tests before application import (accepted, 2026-10-30)

Pytest changes to a temporary working directory before collection, disables dotenv,
removes inherited Gemini credentials and supplies dummy HTTP provider configuration.
This contains current import-time SQLite initialization. Individual integration tests
still use their own temporary databases/files. Test working directories are not the
repository root; use file-relative paths if adding fixtures. No model quality claims
may be based solely on mocks or stored predictions.

## Milestone 1 rollout and rollback

No schema migration, dependency installation or data rewrite is required. Existing
auto-accepted records need explicit review; unknown-schema or malformed records
remain ineligible. Legacy API consumers must migrate from the retired endpoint.
Rollback means reverting only this milestone's reviewed code/doc patch on its feature
branch, preserving databases, originals, review history and the user's handoff files.
Older tools will again reject corrected fallback data. Do not restore the unsafe
legacy authority or deploy without an explicit security review. No automatic rollback
or reset command is supplied.

## ADR 005 — Session-owned authority and quarantine (accepted, 2026-10-30)

FastAPI owns opaque, revocable DB sessions; maintained pwdlib/Argon2 handles password
hashing. CSRF is bound to pre-login/authenticated sessions; cookies are Secure by
default and development HTTP is explicit. This avoids extra identity services for a
self-contained local demo. It requires tested session lifecycle/CSRF logic; OIDC/MFA
and account recovery remain later work. FastAPI Users was not adopted because its
maintainers describe it as maintenance-only.

Employees access own documents; reviewers/admins access organization documents. Policies
are organization-shared with staff-only writes. No role crosses organizations. Legacy
resources receive an unassigned scope; bootstrap cannot silently claim them. Original
downloads are scoped and confined to their storage directory. The Next.js bridge relays
session/CSRF metadata and sets no identity/role grants. Account administration is local,
not a connection to a real external identity provider.

Existing agent/workflow/local rule-review token and network restrictions remain in
addition to authenticated authority. A separate authenticated rule-decision route
supports the UI. Agent scope intersects configured bounds with current DB permissions.
Graph builders receive server principals and deny missing identity.

## ADR 006 — Explicit, forward-only security adoption (accepted, 2026-10-30)

Add a frozen Alembic revision, not startup migrations. New sessions/users/security
events/request limits/workflow ownership and document/policy scope support the new
boundary. Test fresh/repeated upgrade and synthetic legacy preservation, refuse
unrecognized legacy columns, and leave real data untouched until separately reviewed.
The initial security revision has not been released/applied to the user's DB; future
schema changes need new revisions after release. Automatic downgrade is refused to
avoid destroying identity/audit data or restoring insecure access.

Rollback: stop the new app, preserve DB/original/checkpoint backups, restore only a
reviewed code/database combination in isolation, and invalidate exposed sessions. Do
not run older unprotected endpoints against newly owned private records. Ownership
assignment/import tooling remains explicit follow-up; no destructive reset is shipped.

## ADR 007 — Bounded parsing and direct security evidence (accepted, 2026-10-30)

Structural validation/parsing runs in a disposable child with no app keys in its
environment, input/page/pixel/expansion limits and a deadline. Timeouts kill only its
owned process tree. This contains common resource failures but is not an OS security
sandbox; container memory/network controls and durable work remain milestone 3 work.

Retain component tests with explicit synthetic identity and separately test real
Argon2/cookie/CSRF/RBAC paths without authorization overrides. Add Playwright production
bridge journeys using an ephemeral migrated backend and public synthetic fixtures.
Use installed Edge locally; CI defines Chromium installation. Pinned additions:
pwdlib[argon2] 0.3.1, Alembic 1.20.1 and @playwright/test 1.64.1; uvicorn is also
listed in CI requirements for browser fixture startup. No new paid service is needed.

References: [FastAPI passwords](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/),
[OWASP CSRF](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html),
[Alembic SQLite migrations](https://alembic.sqlalchemy.org/en/latest/batch.html),
[Playwright browser channels](https://playwright.dev/docs/browsers),
[FastAPI Users status](https://fastapi-users.github.io/fastapi-users/latest/).
## ADR 008 — Automatic policy rules and account profiles (2026-10-30)

- Reuse stored source chunks internally, but extract the entire bounded policy in one
  provider call. This removes per-chunk user work and supports multiple rules per chunk
  while limiting latency/cost. Input is capped at 30,000 characters; large-policy durable
  batching is deferred rather than silently truncating the source. No new dependency.
- Keep deterministic verification and explicit human decisions. Bulk approval submits
  exactly the displayed ID snapshot and uses one transaction, preventing partial approval
  on conflict and excluding rules introduced after confirmation. Per-rule audit remains.
- Names are mutable display metadata; IDs remain authoritative in stored reviews. Resolve
  labels within the resource's organization and use unknown/unnamed fallbacks. No email,
  organization or role changes through self-profile updates. Personal aggregates avoid
  returning underlying document/account rows; admin account count is explicitly org-wide.
- Password changes reauthenticate, rate-limit and rotate/revoke credentials. Keep this
  browser signed in with a new cookie while terminating other sessions. Forgotten-password
  recovery and SSO remain production follow-ups.
- The additive migration preserves account hashes, sessions, original references and
  legacy ownership quarantine. It is forward-only; rollback requires a reviewed backup.
  Tests use synthetic databases and a synthetic model only. No real database migration,
  model call or deployment is part of this implementation verification.

## ADR 009 — Account-derived investigation scope (2026-10-30)

The development-era document/policy ID environment lists are superseded as a source of
scope. Authenticated database ownership/organization checks now supply permissions;
keeping manual ID lists after authentication made normal uploads unusable and stale
configuration produced misleading denial. Old ID settings are ignored, with no default
grant to legacy/unassigned resources.

The UI loads existing scoped APIs and presents filenames, selecting an available pair.
Optional scalar `document_id`/`policy_id` request fields are selections, never grants.
Both must be provided together and currently authorized; unknown/denied pairs give a
generic 404 before any model construction. Tool scope is narrowed to exactly that pair,
including for staff who can normally inspect other organization documents. Question-only
callers retain account-derived scope up to 50 documents/policies; larger collections must
select a pair to bound model context. Unknown permission/role/model fields remain forbidden.

No schema or dependency changes. Existing production/loopback/token/session/CSRF guards
and deterministic review/source checks remain. Tests exercise actual sessions and the
gateway/backend/tool/evaluator pipeline with synthetic Gemini, without touching real data
or calling an external model. The development UI itself is not an authorization boundary.

## ADR 010 — Durable jobs, PostgreSQL and Arabic foundations (2026-10-30)

Use a database queue rather than adding Redis/Celery to this small single-host project.
Upload validation and original saving precede one resource/job transaction; processing
then runs outside the request. PostgreSQL claims use SKIP LOCKED, SQLite conditional
updates. A 180-second lease, three attempts and a final token/expiry fence prevent stale
workers from committing business results. Execution is at least once; remote requests
can be billed again after a crash. Retry preserves verified approvals through deduplication.
Model generation precedes business write locks; the returned draft is still untrusted
and reverified against stored chunks inside the fenced completion transaction. This
keeps local SQLite writes responsive while a provider is slow.
An embedded worker is the local default; Compose uses a separate process, with a compact
embedded profile for smaller machines. More advanced scheduling/heartbeats await measured need.

Add pinned psycopg binary support without replacing SQLAlchemy/Alembic. Keep SQLite
LangGraph checkpoints on a persistent application volume while business ownership/jobs
use PostgreSQL. This minimizes migration/dependency risk but limits horizontal checkpoint
scaling; a PostgreSQL saver needs separate compatibility and concurrency verification.
Import is explicit, rehearsal-first, current-schema/empty-target only, preserves IDs and
audit, verifies originals and excludes sessions. Database rollback cannot roll back newly
copied files; failed imports must be rehearsed again into a new empty destination.

Runtime dependencies are pinned separately from the heavier experimental retrieval stack.
Containers install both English/Arabic Tesseract packs, use private networking and limited
non-root services; inference is disabled by default. Configuration validation and actual
PostgreSQL restart tests are observed locally. Both container profiles subsequently passed
clean builds, startup, authenticated HTTP intake and full-service restart verification;
CI uses the same isolated runner to repeat those checks.
Arabic support is required across later milestones, starting here with bounded UTF-8
ingestion, explicit OCR language selection, Unicode persistence and automatic text direction.
English monetary rule verification and classification still limit Arabic semantics; do
not present these foundations as measured bilingual quality. See ARABIC_SUPPORT.md.
