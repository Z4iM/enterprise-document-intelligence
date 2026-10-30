# Changelog

## Unreleased — Milestone 4 (2026-10-30)

- Restored the overview introduction's purple gradient and increased text contrast;
  replaced an unsupported gradient class with an explicit CSS gradient and solid fallback.

- Restricted name editing to administrators, including the self-profile API; employee
  and reviewer profiles retain assigned names, activity and password options.

- Fixed login errors masking a backend CSRF/configuration failure as an unreachable
  frontend proxy. Preserve HTTP status/detail and reject malformed CSRF responses
  before submitting mutations; session/HTTPS/CSRF enforcement remains intact.

- Added session/CSRF/organization-scoped bilingual source search, exact citations,
  independent durable indexing and staff-only reindex/removal with completion fencing.
- Added pinned optional local ONNX embeddings, BM25/cosine/RRF, bounded candidate scans,
  incremental vector reuse and explicit keyword fallback; no model downloads on requests.
- Added policy-library search, maintenance confirmation and unchanged-source quotations.
- Added fixed 32-source/40-query bilingual benchmark with measured baselines and explicit
  relevance/Arabic abstention limitations. See docs/RETRIEVAL.md and verification evidence.
- Added derived-table migration, retrieval security/PostgreSQL/browser/container checks;
  preserved approved-rule authority, original files and development investigation guards.

## Unreleased — Milestone 3 (2026-10-30)

- Added PostgreSQL/psycopg support, dialect-correct persistent rate limits and a pinned
  runtime dependency snapshot without heavyweight legacy retrieval packages in containers.
- Added durable ingestion jobs, atomic claims, bounded attempts/backoff, abandoned-lease
  recovery, transactional completion fencing and scoped status/retry APIs.
- Default local processing runs an embedded worker; Compose supports separate-worker
  and compact profiles. Uploads return 202 and UI processing states/polling/retry replace
  synchronous success assumptions. Only completed documents enter the review queue.
- Added non-root application Dockerfiles, private PostgreSQL/API networking, loopback
  frontend exposure, mounted local credentials, migrations/readiness, persistent originals/
  checkpoints and resource limits. Both profiles passed local build/start/full-restart checks.
- Added read-only rehearsal and explicit no-overwrite SQLite import, preservation of IDs/
  hashes/audits/ownership/checkpoints, session revocation, job recovery and PG sequence repair.
- Added Arabic as a release requirement, UTF-8/JSON/filename preservation tests, bilingual
  OCR configuration with explicit missing-pack failure, and RTL-safe evidence display.
- Added real PostgreSQL and process-restart verification, safe import/queue regressions,
  background-worker browser journeys and container/PostgreSQL CI definitions.
- Closed the Docker runtime gate with an isolated serial-build runner, both processing
  profiles, authenticated frontend-bridge uploads, original/session persistence and durable
  LangGraph resume after full-service restarts. Retains stopped synthetic test volumes;
  never loads user env/data. Frontend image builds also enforce TypeScript checks.

## Unreleased — Investigation scope usability (2026-10-30)

- Removed the manual investigation resource-ID environment configuration requirement.
  Scope now comes directly from authenticated account/organization permissions.
- Investigation displays document/policy selectors by filename, chooses available defaults,
  explains empty/review-required states and submits only a selected pair plus the question.
- FastAPI rechecks selections and restricts agent tools to that pair. Forged IDs/grants,
  cross-user/cross-organization access and changes in ownership remain denied.
- Stale legacy ID environment values are ignored. Production, loopback, shared-token,
  session/CSRF, source verification and explicit human review guards remain intact.
- Added real-auth scope regression tests and gateway tests, including the complete
  gateway/backend/tool/evaluator pipeline with a synthetic Gemini client and no ID setup.

## Unreleased — Investigation availability fix (2026-10-30)

- The production investigation page now explains the existing development-only
  restriction and disables its form rather than inviting a request that returns 404.
- Local development additionally checks frontend enablement/token presence server-side;
  no secret value enters client props. Remaining backend 404s get an actionable message.
- Retained production/loopback/token/session/CSRF/resource guards and documented the
  private local setup. Added a browser regression for unavailable UI and direct 404 denial.

## Unreleased — Milestone 2 product follow-up (2026-10-30)

- Policy upload automatically extracts multiple rules across all source chunks in one
  bounded model call; every draft is schema/source verified and remains pending.
- Added confirmed, atomic bulk approval of explicitly selected verified rules, plus
  persisted extraction status, failure/retry UI and retry deduplication.
- Added editable user names, scoped audit/reviewer name resolution, a compact profile
  icon/menu, personal activity by role and administrator name management.
- Added current-password-verified password changes with rate limits, credential rotation,
  revocation of old sessions and redacted security events.
- Added forward-only profile migration and synthetic integration/browser regression tests.

## Unreleased — Milestone 2 (2026-10-30)

- Added hashed opaque sessions, Argon2 passwords, login/logout, CSRF/origin checks,
  active-account enforcement and persistent request/login limits.
- Scoped business routes, downloads, policy selections, agent scope and workflow
  ownership by organization/identity; server sessions supply reviewer attribution.
- Added authenticated policy library, source downloads, atomic rule decisions and
  administrator account creation/disable with session revocation.
- Added frozen Alembic adoption; legacy resources/checkpoints are quarantined and
  real data is not automatically migrated. Removed schema mutation on app import.
- Added byte/type/filename/archive/page/pixel/time/concurrency limits and disposable
  parser workers; bounded model extraction input and sanitized failure logs.
- Added login/account/policy UI, cache clearing, browser journeys and corresponding CI
  definitions. Fixed required-action rendering to match the backend object contract.

## Unreleased — Milestone 1 (2026-10-30)

- Unified API, agent-tool and workflow document eligibility; explicit human review is
  required, including formerly auto-accepted documents.
- Added strict correction validation and fallback recovery while preserving extraction
  provenance and before/after audit records.
- Fixed TXT type dispatch and exposed TXT in upload pickers.
- Retired model-led validation API with HTTP 410; approved-rule evaluation is unchanged
  except for the stricter document review boundary.
- Corrected workflow capability labels and policy-not-found messaging.
- Isolated pytest from development data/dotenv; added trust-boundary lifecycle regressions.
- Added setup, architecture, roadmap, decisions and repository engineering instructions.
