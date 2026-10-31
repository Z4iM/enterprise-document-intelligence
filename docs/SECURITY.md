# Security contract — Milestone 3 (2026-10-30)

M4 extends this contract to search/citation/index routes: session/CSRF, organization/policy
scope before ranking, staff-only maintenance, cancelled leases on removal, current-source
hash/offset checks and bounded corpora. Retrieved instructions remain inert data; search
does not activate rules. Local model files are administrator-configured, verified against
their manifest and never downloaded on requests. See [limits](RETRIEVAL.md).

## Identity and authority

M6 diagnostics are read-only, administrator-only and organization-filtered before
aggregation/trace reads. Browser/model correlation headers cannot select trusted trace
identities. Logs/spans contain no source/prompt/response/credential/identity data; strict
formatting discards raw messages and tracebacks. Telemetry is best effort and has no
business authority. CI audits runtime dependencies and fixable high/critical image
findings, with full-SHA actions and checksum-pinned scanner tools. See
[observability and scan scope](OBSERVABILITY.md); this is not an independent security audit.

M5 specialist intake/resume retains development flag, loopback, private token, sessions,
CSRF and scoped resources. Each node/tool reloads the active account and permission scope.
Role-specific tool allowlists reject model-supplied scope/approval arguments before
dispatch. The final evaluator reloads all approved rules; stored verified flags alone
are insufficient without current source-semantic revalidation. Production Next.js
workflow gateway is disabled regardless of feature flags.

Checkpoint publication shares the queue's unexpired-lease transaction. Stale attempts
cannot publish a head; missing canonical backups fail closed. Supporting evidence is
same-organization/same-uploader, reviewed and attested only by active Reviewer/Admin.
Immutable attestations bind current inputs; changed source/facts/access invalidate them.
Neither model output, workflow resume nor documentation attestation grants expense
approval. Generic documentation requirements need clarification. See SPECIALISTS.md.

Only administrators may change display names, including their own. Both self-profile
and organization-scoped user-management writes enforce this on the server. Employees
and reviewers can read their profile/activity and change their password, but cannot
rename themselves through direct requests or injected role fields.

FastAPI owns opaque sessions. Only SHA-256 verifiers of random 256-bit session and CSRF
tokens are persisted. Passwords use pwdlib/Argon2; local new accounts require 12–128
characters. No token is stored in browser localStorage. Login rotates/revokes the
pre-login credential; logout and account disable revoke sessions. Absolute lifetime is
8 hours with a 30-minute idle limit; anonymous login challenges expire after 10 minutes.

Production is the default cookie mode: `__Host-edi_session`, Secure, HttpOnly,
SameSite=Lax, Path=/ and no Domain. Explicit development uses `edi_session` over local
HTTP. Production CSRF initialization refuses missing/non-HTTPS origin configuration.
Unsafe requests require a session-bound CSRF header and permitted Origin when present;
cross-site Fetch Metadata is rejected. Login also requires the pre-login CSRF challenge.
SameSite alone is not the CSRF defense. No permissive CORS middleware is installed.

The Next.js bridge forwards only session cookies, CSRF and origin metadata to a fixed
server-configured backend. It does not supply roles, ownership or browser credentials
for dev APIs. SessionGate clears query data on logout/expiration; backend permission
checks remain authoritative. Invalid request errors exclude submitted values/passwords.

| Capability | Employee | Reviewer | Admin |
|---|---|---|---|
| Upload document | Own organization/identity | Own identity | Own identity |
| Document/detail/original/audit/history/evaluation | Own documents | Organization documents | Organization documents |
| Review document fields | Denied | Organization | Organization |
| Read policy library/rules/original | Organization | Organization | Organization |
| Upload policy / extract / decide rules | Denied | Organization | Organization |
| Manage accounts | Denied | Denied | Organization; cannot disable self |
| Agent/workflow operations | Authorized resources plus existing dev guards | Same | Same |

No role is a cross-organization superuser. Reviewer identity is derived from the session;
a submitted reviewer name cannot impersonate an account. Rule review verifies source
support before an atomic pending→approved/rejected transition. Competing reviews cannot
overwrite the first decision. Field review never grants expense approval or payment.

Lists, URL IDs, body-selected policies, original downloads and citations use scoped
resources. Cross-scope IDs return 404; malformed IDs cannot expand scope. Agent tools
still enforce exact argument keys/allowlists. Investigation scope comes from current
session/database permissions, with optional paired document/policy selections that can
only narrow that scope. The backend rechecks both IDs before creating a model client;
legacy environment ID lists are ignored. Unknown selection IDs receive the same generic
404 regardless of existence. Question-only legacy callers are bounded to at most 50
authorized documents/policies; larger scopes must select a pair. The UI always selects
a pair by filename. Graph builders default to denial without a trusted principal;
resource-loading/evaluation nodes and workflow status/resume recheck scope. Existing
ownership-free checkpoints and legacy documents are quarantined, not inferred public.

Public routes: root/liveness/readiness, CSRF initialization, login, and autogenerated API
schema/docs. Login is still credential/CSRF checked. All business routes require identity.
Component test identity overrides exist only in tests; no production test-mode bypass exists.

## Budgets and audit

- Persistent SQLite/PostgreSQL counters: 120 authenticated requests/user/minute; 20 login attempts
  per peer/5 minutes and 10/account/5 minutes; 60 CSRF initializations per peer/minute.
  Counter updates are atomic. Forwarded IP headers are not trusted. Behind Next.js the
  peer quota is shared; trusted-proxy-aware production edge limits remain deployment work.
- ASGI bodies: 64 KiB normally, 20 MiB + 64 KiB multipart envelope for upload routes,
  including missing/false Content-Length; 20 seconds to receive. File cap: 20 MiB.
  The bridge separately caps its entire upload request at 20 MiB, including multipart overhead.
- Canonical MIME follows structural parsing, not a caller MIME header. Reject empty,
  binary TXT, malformed signatures, traversal, Windows device/invalid filenames.
- Office ZIP cap: 1,000 entries, 20 MiB expanded total, 100:1 per-entry compression ratio.
  PDF cap: 20 pages; PPTX cap: 20 slides; image cap: 4 million pixels. UTF-8 TXT only.
- Disposable parser process: 45-second deadline, at most two parser jobs/process;
  timeout kills its owned process tree. Parser environment excludes application keys.
  PDF rendering is bounded to one thread/20 pages/1600px and 10 seconds; OCR calls use
  5 seconds each. Extracted text cap: 1 million characters. Model extraction input over
  30,000 characters goes to review-gated fallback instead of sending unbounded text.
  `LLM_PROVIDER=disabled` also falls back without constructing a model network client.
- HTTP/Gemini model requests have 30-second request timeouts. Existing investigation
  call/turn/result limits remain. Durable processing has bounded attempts and leases;
  richer overall model deadlines remain later work.
- Business review/audit records remain scoped. Security events record actor, organization,
  action and relevant account target. Login failure, denial, CSRF failure, login/logout and
  account changes are recorded without bodies, password hashes, raw tokens or source text.
  Provider failures log exception types, not potentially sensitive exception values.

These controls mitigate common misuse. Parser subprocesses share the OS account and
are not a security sandbox or guaranteed aggregate RAM quota. AV/malware scanning,
container definitions add resource/network controls, but local container execution and
edge connection limits are not certified.

## Migration, operations and deferred work

The profile follow-up adds display names (100 characters, no control characters), scoped
personal stats and password changes. Self profile updates cannot change email, role,
organization or another user. Administrator naming is restricted to the same organization.
Current names are resolved for human-readable audit; stable reviewer IDs remain stored.
Unknown/cross-organization actors are displayed as unknown rather than disclosing an account.

Password changes require an authenticated CSRF-protected request, verification of the
current password and a different 12–128-character new password. Five attempts per account
per five minutes are allowed. An optimistic hash comparison prevents concurrent overwrites.
Old sessions are revoked; the current browser gets a fresh cookie/CSRF verifier. Security
events contain neither password nor hash. Account recovery/forgotten passwords remain deferred.

Whole-policy extraction is bounded to one configured-provider call (existing 30-second
provider timeout), 30,000 source characters, 200,000 output characters and 100 drafts.
Model instructions/source IDs are untrusted: every saved rule is independently verified
against a chunk of the selected policy and stays pending. Bulk approval accepts an explicit
ID snapshot, checks every source again and rolls back the complete batch on any conflict.
Extraction failure retains the policy with a redacted retry message. A processing guard
prevents concurrent whole-policy passes; durable jobs recover interrupted background
processing through expiring claims. Processing completion never certifies extraction
recall or full policy coverage. Policies outside the current numeric expense schema still
require manual interpretation; no unverified rule becomes authoritative.

Alembic adopts recognized legacy columns without rewriting originals/rows. Existing
resources stay in `legacy-unassigned`, with no automatically assigned users. New
bootstrap generates a separate organization. Unknown legacy shapes fail preflight.
No startup migration or default account is created. Adoption must be explicitly run
against a reviewed database; the user's real database was not opened/migrated for tests.
The security revision is forward-only to avoid destructive automatic downgrade.

Milestone 3 adds PostgreSQL-aware atomic counters and claim/lease/fenced job completion.
Workers recheck account/resource authority, confined original paths and hashes. Status and
retry routes enforce resource scope and redact errors. SQLite import is rehearsal-first,
read-only at source, empty-target only, hash-verified and excludes old sessions. It never
assigns legacy ownership. Original extraction repeats structural validation after import.
See [persistence](PERSISTENCE.md) for limits and explicit import/startup procedures.

Compose publishes only the loopback frontend; API/DB remain private. App services use
non-root users, read-only roots, dropped capabilities and memory/CPU limits. Per-service
secret files avoid embedded credentials. Both profiles passed Docker build/start/restart
checks with isolated synthetic data. Runtime inspection confirmed non-root app users,
read-only roots, memory caps, loopback frontend binding and no published API/DB ports.
Single-host Compose does
not supply production TLS, restricted egress, high availability or managed secret rotation.

Remaining: retention/purge of expired sessions/security logs;
central production proxy limits; HTTPS/headers/backup/restore/deployment review; stronger
process/container isolation; SSO/MFA/password reset; load/SLO testing; security review.
This milestone is not a production certification, penetration test or public deployment approval.

Design references: [FastAPI password hashing](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/),
[OWASP sessions](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html),
[OWASP CSRF](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html).

## M7 public-source rehearsal and release hold

The showcase preparation tool rejects private paths, credential configuration files,
symlinks/junctions/hard links and existing destinations. It copies public working source,
not user state; the fixed synthetic `tests/data/policy_benchmark.json` is explicitly allowed.
Its path filters are not a semantic secret scanner. Review source and history before release.

The rehearsal discovered three legacy tracked runtime artifacts under root `data/`.
M7 removes them from the tracked index while preserving their original files on disk;
their contents were not inspected. Existing Git history can still contain those artifacts.
**Owner review/history remediation is required before public release**; this milestone
performs no history rewrite, file deletion or publication and makes no claim that old
history is sanitized.

The optional frontend showcase notice labels scripted generation. It grants no permission,
changes no backend scope and never enables production investigation/workflow gateways.
The account-only fixture server is loopback-bound and temporary; its published synthetic
password must never be used to provision a normal or publicly exposed application.


### Current evidence warnings

The policy rules GET response includes read-only current validation and the number
of invalid active approved rules. It uses the same source/semantic validator as
official evaluation, behind the existing session and policy-access checks. It never
mutates approval records or skips invalid approved evidence. Investigation blocker
messages use an explicit server-code allowlist; source quotations, raw exceptions and
model drafts are not inserted into failure messages. Existing authorized policy
quotation views are unchanged.
