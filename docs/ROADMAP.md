# Roadmap and acceptance

Showcase target: **2026-11-06**. Production readiness is a later evidence-based gate.
Milestones stop for review; dates are planning windows, not completion claims.

| Milestone | Window | Status | Acceptance |
|---|---|---|---|
| 1: Trustworthy local lifecycle | Oct 30 | Complete | Consistent API/tool/workflow eligibility; TXT upload; validated fallback correction and durable resume; legacy route retired; full quality gates |
| 2: Identity and security | Oct 30–Nov 1 | Accepted for continuation | Sessions/CSRF/logout/password change; scoped Employee/Reviewer/Admin; names and role-specific personal stats; bounded uploads; automatic policy extraction and confirmed atomic bulk approval; account-derived investigation scope |
| 3: Persistence/recovery | Nov 1–2 | Reviewed and merged | Both Docker profiles built/started/restarted; authenticated HTTP intake; safe synthetic SQLite import; real PostgreSQL; durable jobs/recovery; Arabic Unicode/OCR/RTL foundations |
| 4: Evidence retrieval | Nov 2–3 | Reviewed and merged | Authorized hybrid search; incremental indexing/removal; fixed 40-query bilingual benchmark; English/Arabic Recall@5/MRR/citation/abstention results and baselines |
| 5: Cooperating specialists | Nov 3–4 | Locally verified; awaiting review | Separate bounded tool-choosing roles; durable fenced checkpoints and workflow UI; 40 bilingual fixtures/eight actual scans; narrow Arabic verification; real review/evidence gates; scripted single-agent comparison. General OCR/model quality remains unproven. |
| 6: MLOps/release checks | Nov 5 | Not started | Browser lifecycle test; redacted correlated logs; latency/error/token/cost metrics; evaluation/container CI gates |
| 7: Showcase freeze | Nov 6 | Not started | Independent clean-start rehearsal; screenshots/demo; evidence-supported CV claims and published limitations |

Security, evidence gates and honest verification outrank optional reranking, extra
agents or dashboards. Docker availability/disk headroom and approval turnaround are
schedule risks. If container/clean-start verification cannot run, the showcase definition
of done remains incomplete; document that explicitly.

Milestone 2 investigation usability follow-up: replace manual development ID scope with
current account permissions and document/policy selectors; keep all network/auth/review
guards. This does not implement milestone 5 multi-agent orchestration or authorize
production investigation exposure.

## Release gates

- **English and Arabic document support are required**, including mixed-script text.
  See [Arabic acceptance](ARABIC_SUPPORT.md); model language ability alone is insufficient.
- All backend Ruff/pytest and frontend TypeScript/build checks pass.
- Synthetic lifecycle demonstrates review, approved rule, cited deterministic answer,
  interruption/restart/resume, and an inspectable audit trail.
- All document/policy/file/workflow/tool surfaces enforce real authorization before
  public access; ordinary routes have session/scope checks, with deployment and independent
  security verification still pending.
- CI requires no personal secrets or network model inference.
- Every benchmark states corpus size, model/configuration and limitations.

## Production v1 queue

OIDC/SSO; independent security review and threat model; additional schemas/languages beyond the required English/Arabic coverage;
backup/restore rehearsal; TLS/secrets/retention/deletion; measured load/SLOs;
deployment, rollback and operational runbooks. No production-readiness claim before
these are verified. Real Gemini usage, external changes and deployment need separate
authorization.

## Milestone 1 checkpoint (2026-10-30)

176 backend tests, full Ruff, frontend TypeScript/build and production HTTP smoke
checks passed. See [observed verification](VERIFICATION.md) for scope and limitations.
No schema/dependency changes, live model calls, commits, pushes or deployment.
User approved continuation to authentication/authorization/security.

## Milestone 2 checkpoint

Sessions/RBAC/ownership, CSRF, bounded uploads, authenticated review/rule decisions,
organization policy discovery, local account administration and Alembic adoption are
implemented. Existing development guards are retained. Parser and model input budgets
are enforced; jobs are still request-driven. 235 backend tests and 2 browser journeys passed; evidence is recorded
in VERIFICATION.md. Real data remains unmigrated and legacy ownership remains quarantined.
The user explicitly approved milestone 3 and added Arabic documents as a requirement.
The November 6 showcase remains a conditional target.

## Milestone 3 checkpoint

Implemented PostgreSQL support, pinned runtime dependencies, safe synthetic backup import,
durable ingestion jobs with recovery/fencing, status/retry UI and default embedded local
worker. Compose defines private PostgreSQL/API/worker and loopback frontend, migrations,
readiness, persistent volumes, secret mounts and compact resource limits. Arabic foundations
cover Unicode ingestion/persistence/import, OCR packs/configuration and automatic text direction.
Full backend: 296 passed, 8 opt-in PostgreSQL tests skipped without a supplied cluster;
the dedicated PostgreSQL suite runs separately. Evidence and outstanding gates are in
VERIFICATION.md. Docker build/start/full-service restart verification subsequently passed
for both profiles, including real authenticated HTTP intake and persisted sessions/originals.
The container CI job now uses the same isolated verification runner; remote CI is unobserved.
Milestone 3 was subsequently reviewed and merged. The user approved milestone 4;
its scoped retrieval implementation and measured benchmark are described in RETRIEVAL.md.
Milestone 4 was subsequently reviewed/merged as PR #5; all four remote CI jobs passed.
The user approved milestone 5. Its design, measurements and limitations are recorded
in [SPECIALISTS.md](SPECIALISTS.md); no further milestone or publication is authorized.
