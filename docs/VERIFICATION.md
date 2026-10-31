# Engineering verification — 2026-10-31

[NEXUS EDI](../README.md) · [Documentation guide](README.md)


## Current documentation checkpoint

Observed documentation-refresh checks (2026-10-31):

- Ruff passed; full backend suite **401 passed, 9 opt-in PostgreSQL skipped in 446.91 seconds**. No dedicated PostgreSQL/container/browser rerun was needed for Markdown-only edits; their earlier evidence remains dated below.
- Frontend `npm run lint` passed. A public-source export on D: completed a fresh `npm ci` (zero npm-reported vulnerabilities) and the standard optimized `npm run build`, including TypeScript and route generation. The active application's build directory was untouched.
- The initial sandbox build rejected an external dependency junction under Turbopack's filesystem boundary. That verification-only junction was replaced with a fresh local dependency installation; the standard build then passed. Application code/configuration was not changed to bypass the boundary.
- Checked **23 repository Markdown files** for local link targets and balanced code fences: no issues. `git diff --check` passed; final diff contains Markdown only. Original engineering instruction/handoff files are preserved.
- No real provider inference, migration, private-data inspection, deployment or LinkedIn publication occurred. The user authorized this documentation commit and branch push; remote CI is not a locally observed result.


PR #8 was merged into `main` (merge commit `82ed42c`). The results below retain their original dates and scopes; a merge is not a fresh test run or production certification. The subsequent documentation refresh changes no application code. Its observed verification is recorded with that documentation commit, separately from the M7/UX results.

## UX follow-up — current policy evidence and investigation blockers

Added after the M7 showcase checkpoint on the same review branch.
The policy library reports current source validity independently of historical
approval. Invalid active approved rules are individually flagged and block policy
use. Read-only checks share the official loader's validator; no approval or source
record is changed. Investigation replies use allowlisted blocker/stop codes and
link to policy/document review; unknown diagnostics stay generic and drafts remain hidden.

Observed in the isolated public-source sandbox on D:, with personal dotenv loading
disabled and synthetic fixtures only:

- Full Ruff passed. Full backend: **401 passed, 9 opt-in PostgreSQL skipped in
  209.74 s**. New coverage includes stale English/Arabic source semantics, current
  versus historical approval, preserved records, blocked evaluation, specific stop
  reasons and refusal to expose unrecognized error/draft content.
- Frontend TypeScript and optimized production build passed. Production Playwright:
  **30 passed, 4 expected development-only skips in 46.6 s**. Development browser:
  **2 passed in 52.0 s**, including the existing Arabic specialist review/resume
  journey and the new warning/actionable-investigation display test. English/Arabic
  showcase journeys: **2 passed in 1.2 min** (33.8 s / 27.3 s).
- The new display test supplies a synthetic stale-validation API response to exercise
  historical badges, warning text and review links without modifying fixture approvals
  or calling a model. Backend tests exercise the real read-only verifier and API payload.
  Its first label assertion assumed title case; it was corrected to match the existing
  badge presentation. This did not change product behavior or weaken a check.
- Final warning-display rerun passed **1/1 in 19.6 s**; both new UI captures were
  visually inspected. Final TypeScript and staged/unstaged diff checks passed.

At local verification, no new dependencies or schema changes, live inference,
real-data mutation, commit/push, deployment or production-readiness claim. Existing Docker results belong
to the M7 checkpoint; container images were not rebuilt for this follow-up. Restart
the local backend to load these code changes, then refresh Policies/Investigation.
Previously invalid rules remain blocked until new source-backed candidates are
explicitly reviewed; retrying extraction on an existing copy does not erase approvals.

## Milestone 7 local showcase checkpoint

Implemented on `feat/edi-showcase-release`, based on M6 merge
`a264ec8ec62e2d3f5f606387ed6a114688785ab1`. M6 remote run
[41151690300](https://github.com/Z4iM/enterprise-document-intelligence/actions/runs/41151690300)
passed all five jobs. **At this local checkpoint M7 was uncommitted/unpushed;
its new CI step had not run remotely.** No deployment, public posting, finished video or paid
creative generation was performed.

- A public working-source export on D: installed a **new Python virtual environment
  and fresh `npm ci` dependencies**. `pip check` passed; npm reported zero
  vulnerabilities. This is a source export with an explicitly dirty base manifest,
  subsequently synchronized for fixes/materials, **not a remote clean-clone or
  cold-cache/network reproducibility claim**. No user dotenv/database/uploads/models
  were copied. Export refusal, overwrite/nesting denial, hard-link denial and install
  environment filtering have six synthetic regression tests.
- Fresh full backend: **391 passed, 9 opt-in PostgreSQL skipped in 169.86 s**.
  Dedicated isolated PostgreSQL: **9 passed in 17.24 s**. Full Ruff, frontend TypeScript
  and optimized production build passed. No schema/dependency change in M7.
- Production browser suite: **30 passed, 3 expected development-only skips**;
  the existing Arabic specialist development journey separately passed, as did the
  **two new English/Arabic empty-account showcase journeys**. These perform actual
  policy upload/source verification/confirmed approval, keyword evidence retrieval,
  receipt intake, human correction, reviewed documentation, workflow pause/resume,
  deterministic outcome, audit/trace lookup, role denial and colleague ownership
  denial. Native UTF-8 fixtures do not certify scan/OCR or live Arabic reasoning.
- Docker run **`c71031202601`** passed **all default and compact profile checks**
  from the exported source, including HTTP intake/search/original access, persisted
  sessions, processing, specialist checkpoint, full restart and reviewed resume.
  Both profiles reported Arabic text preservation and **zero real model calls**.
  Only owned verification services were stopped; images/volumes were retained.
- The existing release-gate reproduction passed **16 regression checks**; the
  product-quality gate remains **false**. No new OCR, retrieval-quality or live-model
  accuracy measurement was made. Prior benchmark limitations still apply.
- Six raw screenshots from passing synthetic browser journeys were visually reviewed,
  including 390px Arabic. Visible banners disclose scripted generation; policy/source
  review and deterministic evaluation remain real. See [showcase guide](SHOWCASE.md),
  [script](DEMO_SCRIPT.md), [portfolio drafts](PORTFOLIO.md) and
  [machine-readable evidence](benchmarks/showcase-m7.json).

The rehearsal found and corrected three test/operational issues: a workflow button's
accessible name includes its status; navigating before the review POST completed
raced eligibility checks; and a five-second login UI assertion could expire while
sign-in was pending. Tests now wait for successful HTTP acknowledgements and recorded
review state. No authorization, approval or eligibility rule was loosened. Automated
Next.js servers now bind explicitly to `127.0.0.1`. Final exporter tests passed
**6/6 in 4.87 s**; Ruff and staged/unstaged diff checks passed. Docker Desktop
was restored with only its original idle BuildKit container; demo ports were closed.

**Public release hold:** export initially refused three legacy tracked root `data/`
artifacts before creating its target. They were removed from Git's index while all
three remain on disk; their contents were not inspected and history was not rewritten.
Their presence does not establish whether their contents are private. Owner review
and any necessary history remediation are required before publication. A repository
license must also be chosen; none was silently added. This milestone does not certify
production readiness or remove the M6 security/product-quality limitations.

## Milestone 6 checkpoint

Implemented on `feat/edi-mlops-release-checks`, based on merged M5 PR #6
(`a07e08b`). M5 remote workflow 41134793582 was observed successful. The user
authorized the M6 commit, push and pull request. **M6 awaits PR review**; local
verification below does not assert that its new remote CI has passed.

PR #7's initial workflow **41150046020** subsequently passed the backend, frontend/browser,
PostgreSQL and container/image-scan jobs. The dependency-audit job correctly failed on
four advisories in `pyasn1==0.6.4`; the same result was reproduced locally with a fresh
audit. The runtime pin is updated to **0.6.5**, the upstream security patch; the identical
strict full-manifest audit now reports **zero advisory entries**, with no ignore rules
or CI-gate changes. Earlier scan reports remain historical snapshots rather than current
security guarantees. See [remediation evidence](benchmarks/security-m6-ci-fix.json) and
[PR checks](https://github.com/Z4iM/enterprise-document-intelligence/pull/7/checks) for the
latest remote result. The patched local environment passed `pip check`, full Ruff,
**385 backend tests (9 opt-in PostgreSQL skipped) in 145.96 s**, frontend TypeScript
and the optimized production build. No application/authorization behavior or audit gate
was changed. Verification below records the original M6 checkpoint.

No deployment, live model inference, private environment/document inspection or real-data
migration. Verification accounts, files, databases and service projects were synthetic.

- Full Ruff passed. Final backend: **385 passed, 9 opt-in PostgreSQL skipped in
  156.54 s**. Dedicated current-code PostgreSQL: **9 passed in 15.56 s**, including
  migration/model parity and checkpoint recovery. New tests cover trace isolation,
  content-free logs, unknown-versus-zero usage, pricing coverage, best-effort/capped
  persistence, disabled telemetry, format-specific parser startup, release gates,
  scanner checksum refusal and replacement-worker claim fencing before dispatch.
- Frontend TypeScript and optimized production build passed in a public source copy
  on D: without private environment files. Production Playwright: **30 passed,
  1 expected development-only skip in 49.4 s**. Final operations-specific mobile/role
  checks: **3 passed in 12.6 s**. Development Arabic specialist journey: **1 passed
  in 44.8 s**, including actual upload-reference to queued-job trace correlation.
  Generation alone was scripted. Final desktop/390px Arabic and mobile operations
  screenshots were visually inspected; quotations and review states are readable.
  The operations latency table scrolls within its card on narrow screens.
- Both container profiles passed all functional checks on run `c61031202604`, after
  the final stale-claim guard: readiness, migrations, OCR packs, HTTP upload/search/
  citations/originals/sessions, processing, specialist pause, full restart, review,
  resume and normal cleanup. Runtime image hardening and scans are recorded below.
- Refreshed multilingual ONNX retrieval: **87.5% hybrid Recall@5**, quotation integrity
  **100%** on the same fixed 40-query synthetic corpus. Arabic unanswerable abstention
  remains **50% (2/4)**. Native extraction passed all 40 supported templates. Actual
  M6-image OCR on eight rendered scans remains **75% English / 50% Arabic** scanned
  field accuracy, four scans/language. Arabic CER/WER: **0.4103 / 0.4033**, scanned
  policy verification **0/1**. These are development fixtures, not held-out quality.
- Low-memory failures were observed and investigated: concurrent Docker/native checks
  exhausted host commit, causing parser/auth failures and one CLI cleanup failure.
  Serial reruns, with the verified-idle Docker engine temporarily stopped for native
  checks, passed. Parser imports now load only the requested format; password hashing,
  parser limits, source/review gates and authorization were not weakened. No user apps,
  images or volumes were deleted. See [resource guidance](OBSERVABILITY.md#resource-aware-verification).

Final image hardening was rechecked on run `c61031202605`: **both profiles passed**
with normal cleanup. The final frontend has no global npm/npx tree and starts with
Node v22.23.4. The backend filesystem layers are identical to the scanned `04` image;
only image configuration metadata differs. Linux Grype 0.121.0 using database
v6.1.10 (built 2026-10-30) passed the fixable high/critical gate on both images:
backend has 11 medium, 1 low and 1 negligible fixable matches; frontend has none.
Unfixed findings remain, including Debian Bookworm util-linux CVE-2026-53615.
The initial Windows scan raised duplicate binary/backport matches; the same archive
and database passed the Linux cross-check, consistent with [upstream issue #5466](https://github.com/anchore/syft/issues/5466).
No custom ignore rules were added. Runtime pip-audit reported **0 advisory entries**;
application runtime npm audit reported **0 vulnerabilities**. Five pinned Python
packages were patched. See [machine-readable scan scope/results](benchmarks/security-m6.json).

The final release command passed **16/16 regression checks**. Requiring product quality
correctly exited **1**: only 1/8 quality checks passed. Small/weak OCR scan coverage,
Arabic abstention, missing held-out data and unmeasured live-model quality/cost remain
explicit blockers. [Raw release reports](benchmarks/release-m6/release.json) retain
corpus/script versions, per-language metrics, real timing and unknown provider usage.
Artifact hashes normalize CRLF to LF so Git checkouts preserve their integrity.
This is an implemented release gate, **not product-quality or production approval**.

Final workflow YAML/action-pin, public JSON/report-hash and changed-file credential-pattern
checks passed, along with `git diff --check` using repository line-ending settings.
The credential-pattern check is limited; it is not an independent security assessment.
Docker Desktop was restored; only its original idle BuildKit container remained running.

Telemetry is content-free, bounded and best effort, not an authoritative audit, billing
ledger or load-test SLO. The new `20261031_observability` migration was exercised only
on synthetic databases. Back up the selected real database before an explicitly chosen
migration; startup does not migrate it. To demonstrate M6 after migration/startup, sign
in as an administrator, open **Operations**, upload a synthetic document and inspect
its request/queue trace. Employees/reviewers are denied the operations API/UI. Missing
provider usage/prices remain **Unknown**.

## Milestone 5 checkpoint (historical local checkpoint)

Implemented on `feat/edi-specialist-workflows`, based on merged milestone 4 PR #5
(`5a7bb53`). M4's four remote CI jobs were subsequently observed passing. This milestone
is uncommitted/unpublished and awaits user review; **M5 remote CI is not observed**.
No deployment, live Gemini inference, private environment inspection or real-data
migration. All accounts/documents/DBs/volumes used for verification were synthetic.

- Full Ruff passed. Final full backend: **363 passed, 9 opt-in PostgreSQL skipped**
  in **174.72 s**. Dedicated current-code PostgreSQL: **9 passed in 15.57 s**, including
  schema/model parity and specialist worker pause/reopen/resume using PostgreSQL records.
- Native frontend TypeScript (`npm run lint`) and optimized build passed in a public
  source copy on D: without `.env.local`. Production Playwright: **27 passed, 1 expected
  development-only skip in 44.2 s**. Development Arabic specialist journey: **1 passed
  in 41.5 s** in the final screenshot run, including authenticated upload, whole-policy extraction/review,
  corrected Arabic fields, existing receipt attestation, original-file download, worker
  checkpoint resume, cited outcome and 390px no-horizontal-overflow check. Generation
  alone was scripted; no live-model quality claim.
  Desktop and mobile screenshots were visually inspected: readable Arabic quotations,
  intact review states and no clipped/overflowing content.
- Both Docker images built; default **and** compact profiles passed migrations/readiness,
  OCR pack checks, worker processing, specialist pause → full-service restart → review →
  resume, authenticated HTTP upload/index/Arabic search/citation/original/session/restart
  checks. Final isolated run ID: `b51030202602`. Config validation passed both profiles.
  Workflow flag is enabled only in the runner's owned verification override; normal
  Compose defaults and production frontend guards remain unchanged.
- Security regressions exercise disjoint tools, injected role/scope/final approval fields,
  bounded provider failure, revoked actor/reviewer access, source-semantic tampering,
  same-uploader evidence, idempotent replay, immutable attestation history, stale evidence,
  missing canonical backups, read-only checkpoint import and an expired attempt racing
  a replacement worker. The expired attempt could not publish over the canonical head.
- Native bilingual regression: **40 templates, 20 per language**; actual application OCR
  also ran on **eight rendered scans**, four/language, with no network/real data.
  Supported native fields/policy verification passed 100%; English scanned field exact
  accuracy **75%**, Arabic **50%**; Arabic OCR CER/WER **0.4103/0.4033**, false abstention
  **43.75%**, Arabic scanned policy verification **0/1**. These are development templates,
  not held-out enterprise accuracy. Accurate general Arabic OCR remains unfinished.
- Existing investigator versus specialists: **12/12 canonical outcomes each**, using
  scripted adapters; **34 versus 50** scripted model calls. No demonstrated generative
  accuracy gain; live tokens/cost/provider latency are unmeasured. Raw corpus/evaluator
  hashes, configuration and per-case results are in `docs/benchmarks/*-v1.json`.
- Pinned SDK client constructed/closed with a synthetic key without network inference;
  native `pip check`, final diff/credential-pattern review and `git diff --check` passed.
  This is not an independent penetration test or dependency-vulnerability audit.

Observed logs are ignored `.local/m5-complete-*.log`; frontend logs/screenshots live in
the D: verification copy. Owned verification services were stopped; synthetic volumes,
images and checkpoint artifacts retained. No new model download/runtime dependency.
See [architecture, setup and limitations](SPECIALISTS.md). Next milestone 6 requires
separate approval; no automatic continuation, commit, push or deployment.

## Milestone 4 checkpoint (2026-10-30, local working branch)

Local verification used `feat/edi-authorized-retrieval`, based on merged `fb1487c`,
before publication of the milestone PR. No deployment, live Gemini call or real
user-data migration. All test sources/accounts are
synthetic; databases/volumes isolated. No private environment files were read.

- Full Ruff passed. Full backend **315 passed, 9 opt-in PostgreSQL skipped** in 162.76 s.
- Final dedicated PostgreSQL run **9 passed in 13.91 s**, covering fresh/repeated
  migrations, metadata compatibility, import, sessions, retrieval JSON/scope/removal and
  stale indexing completion rollback after removal in a separate transaction.
- Native TypeScript/build passed in a clean D: directory containing selected public
  frontend files and dependencies, excluding private `.env*`. Docker frontend likewise
  passed both checks. **14 Edge/Playwright journeys passed in 46.7 s**, including Arabic
  upload/search/exact evidence/removal/original access and prior auth/approval guards.
- Fixed an observed duplicate React key that duplicated the search form across policy
  changes. A later resource-starved parallel browser run hit a Node allocation failure;
  rerunning with a bounded 512 MB Node heap passed. No application guards were loosened.
- Real pinned local ONNX benchmark: 32 synthetic policies / 40 labeled queries (20 per
  language), keyword/semantic/hybrid comparison. Hybrid Recall@5 **87.5%**, MRR **0.9635**,
  quotation integrity **100%**; Arabic Recall@5 **84.4%**, unanswerable abstention only
  **50% (2/4)**. Relevance precision **43.75%**. See RETRIEVAL.md and raw benchmark JSON;
  quotation integrity does not certify relevance or answer correctness. Percentile
  aggregation uses nearest rank over recorded individual timings, without new inference.
- Clean Linux runtime install and `pip check` passed in Docker. The initial 768 MB API
  cap caused a confirmed Docker OOM during model initialization; the 1 GB cap subsequently
  passed both normal and compact profiles' real-model upload/index/search/citation/
  original/session/restart checks. Owned verification containers were stopped afterward;
  synthetic volumes/images and ignored logs were retained, with no broad Docker cleanup.
- CI now reproduces the keyword corpus without model/network inference and retains
  PostgreSQL, browser and both-profile container gates. M4 remote CI was **not observed
  at this local verification checkpoint**; see the PR checks for subsequent CI results.
- Final TypeScript and production build repeated successfully after backend gates;
  native `pip check` and final diff/credential-pattern review passed. This is not an
  independent security audit or a full dependency-vulnerability scan.

Limits: exact scans cap at 5,000 authorized candidates; no large-corpus/concurrent load
SLO, independent security certification, Arabic semantic extraction/rule interpretation
or generative answer-quality claim. HTTP search concurrency is bounded to one per API
process (429 when busy). Original files/chunk IDs/approvals and investigation dev guards
remain authoritative. Derived index removal is not deletion of policy data.

Demo: migrate a backed-up native DB or start Compose (automatic migrations); configure
the optional local model as documented in RETRIEVAL.md. Upload a synthetic policy as
reviewer, wait for search readiness, ask in Arabic/English, inspect the original, then
confirm removal and verify the original/rules remain. Reviewers can restore indexing.

### Local login error follow-up

Observed running local services: `/health` 200, `/ready` 503 `Database migrations required.`,
and direct/bridged `/auth/csrf` 503 `Configure HTTPS application origins.`. Next.js was
reachable; the request helper caught the CSRF exception and mislabeled it as a proxy
network failure. Preserve backend status/detail through `ApiError`; reject malformed
successful CSRF responses before any mutation. HTTPS/session/CSRF guards remain intact.
Local HTTP requires explicit backend development mode and loopback origins, with the
same database configuration for migration and server. No real database/environment
files, passwords or running server configuration were changed by this follow-up.

Observed: Ruff passed; backend **315 passed, 9 opt-in skips (193.02 s)**; TypeScript and
production build passed in the isolated D: frontend; **17 Playwright checks passed
(59.2 s)**, including three new CSRF/network/error regressions. Diff review/check passed.

### Admin-only name editing follow-up

Restricted POST `/auth/profile` to administrators through the shared authorization
guard; `/admin/users/{id}/profile` retains administrator and organization checks.
Employee/reviewer menus display the assigned name and an admin-managed notice, while
activity, password changes and logout remain available. Admins retain self-name editing
and organization user-name management. Valid direct requests and injected role fields
cannot let non-admins change their persisted name. No schema/dependency change.

Observed: profile/policy subset **25 passed**; full backend **315 passed, 9 opt-in skips
(160.36 s)**; Ruff, TypeScript, production build and diff check passed. **19 Playwright
checks passed (1.2 min)**, including employee/reviewer name-control absence and the
existing admin self-rename/password journey. Verification used isolated synthetic data;
no real accounts were edited. Runtime permission changes require a backend restart.

### Overview contrast and employee document-scope check

Replaced the unsupported overview gradient class with explicit CSS plus a solid purple
fallback, white heading and light lavender supporting text. TypeScript/production build
passed; inspected synthetic desktop/mobile banner screenshots and computed colors.
Ruff/diff checks passed. Four existing employee-isolation cases passed (6.32 s), verifying
own-only document lists and denied peer/foreign details, originals, audit and reviews.
Backend code is unchanged from the preceding 315-test run. Organization policies remain
shared read-only; employee document ownership is separate from policy visibility.

Branch: `feat/edi-trust-baseline`, based on `009cb2e`. Local working changes only;
no commit, push, deployment or real model invocation was performed.

## Observed checks

| Check | Result |
|---|---|
| `.venv/Scripts/python.exe -m ruff check . --no-cache` | PASS, full project |
| `.venv/Scripts/python.exe -m pytest -q` | PASS, **176 tests in 10.82s**; baseline 157 |
| Frontend `npm run build` | PASS, Next.js 16.4.2; reviews/workflows/upload routes generated |
| Frontend `npm run lint` | PASS, TypeScript `tsc --noEmit` |
| Production HTTP smoke: `/reviews`, `/workflows`, `/upload` | PASS, 200 and updated rendered text; TXT accepted and listed |
| Production `POST /api/agent/investigate` | PASS, 404 even with development enable flag and synthetic token supplied |
| `git diff --check` | PASS |

Backend checks used Python 3.12.10. Local frontend verification used Node 24.15.0;
CI targets Node 22. Builds used a temporary copy of current frontend source and the
existing installed dependencies, excluding secret environment files. Generated build
artifacts did not replace the user's development build. The temporary server bound
to loopback port 3197 and was stopped after the checks.

## Regression evidence

`tests/test_review_trust_boundary.py` exercises real API routes, SQLite records,
LangGraph, dispatcher/evaluation tools and the verified answer builder:

- Nine status/method/processing combinations agree across API, tools and graph.
  Rejected, unreviewed, auto-accepted, failed and unknown-method records cannot save
  an official evaluation.
- TXT upload parses real text, uses a mocked inaccurate fallback, interrupts a
  checkpoint, rejects simple fallback approval, persists validated correction and
  before/after snapshots, reopens the checkpoint and resumes to cited requirements.
- Corrected fallback data becomes usable by both the policy API and verified
  investigation while the original extraction method remains `regex_fallback`.
- A mocked model's fabricated payment approval is absent from the official answer.
- Invalid types/unknown correction fields return 422 with no saved review mutation.
- Empty/malformed reviewed data stays unavailable to tools and evaluation.
- Auto-accepted documents appear in the review queue. The retired legacy endpoint
  returns 410 without saving an evaluation or requiring a RAG/model import.

Existing tests continue to cover token/local guards, bounded tools, tampered evidence,
policy boundaries, missing rules, durable checkpoint reopening and forged resume
signals. Historical positive fixtures now declare a supported document type and/or
explicit approved review; assertions were not removed to permit unreviewed data.

## Not run / remaining limitations

- Clean dependency installation, Node 22 execution, remote GitHub Actions, container
  checks, browser interaction/visual QA and OCR binary execution: **NOT RUN** in this
  milestone. Production HTTP checks are not a full browser journey.
- Live Gemini inference, model quality/cost, retrieval benchmarks and external
  services: **NOT RUN**. Mocks do not establish live model quality.
- Authentication, verified reviewer identity, ownership, CSRF/rate limits and upload
  resource hardening remain milestone 2 work. Ordinary APIs remain local-only in use.
- No schema or dependency changes, migration, destructive reset or data rewrite.
  Unknown-schema records still abstain and require future remediation tooling.
- Final diff was reviewed for the shared trust boundary, retained dev guards,
  credential exposure and unrelated changes. This is not a full security audit or
  repository-history secret scan.

## Reproduce the synthetic demo

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_review_trust_boundary.py
```

This needs no personal credentials or approved local policy database. Pytest uses a
temporary working directory before application import, disables dotenv, removes the
inherited Gemini key and seeds isolated synthetic records. See README for loopback
browser setup and ADRs for the contract change/rollback implications.


# Milestone 2 verification — 2026-10-30

Branch: `feat/edi-auth-security`; milestone 1 working changes were retained. No commit,
push, deployment, real-account bootstrap or migration of the user's database was run.

| Check | Observed result |
|---|---|
| Full-project Ruff | PASS after final import correction |
| Full pytest | **235 passed in 45.63 seconds**; milestone 1 had 176 |
| Python dependency compatibility | `pip check`: no broken requirements |
| Frontend TypeScript | PASS, `npm run lint` |
| Production frontend build | PASS, Next.js 16.4.2; all existing routes plus `/users` |
| Playwright on installed Edge | **2 passed in 24.6 seconds** on the final no-network-model fixture |
| npm production-dependency audit | Zero reported vulnerabilities |
| CI YAML | Parsed successfully; backend and frontend/browser jobs defined |
| Diff whitespace check | PASS |

Local runtime: Python 3.12.10, Node 24.15.0; CI targets Python 3.12/Node 22. Production
build/type checks ran against a temporary frontend copy without secret files. Source
and manifest hashes were compared to the workspace: no differences. Browser fixture
servers used only loopback ports 3197/8197 and were stopped by the test runner. No
private data or real model credentials were required. `LLM_PROVIDER=disabled` avoids
even loopback model requests in the final browser fixture.

## What the tests establish

- `tests/test_security.py` uses real Argon2 verification, cookies, CSRF and database
  permissions with no authentication dependency overrides. Anonymous business routes,
  same-organization peer downloads, cross-organization resources, employee review/
  rule approval, forged reviewer attribution and organization injection are tested.
- Session fixation rotation, expiry, idle expiry, logout, account disable/revocation,
  secure cookie attributes, origin/CSRF denial and persistent login throttling are tested.
  Invalid input responses do not echo submitted secret markers. Standalone mounting of
  the auth router also denies anonymous access.
- Agent scope is the configured/authorized intersection; malicious questions or extra
  permission arguments cannot expand it. Existing dispatcher/tool/injection/evidence
  regressions still run. Workflow ownership and linked-document permission are checked
  again after checkpoint creation and before status/resume.
- Rule review verifies source evidence and atomically consumes pending state. A
  simultaneous two-reviewer test permits one decision and rejects the competing one.
- Upload tests cover filenames (including Windows devices), traversal, malformed file
  types, spoofed MIME, byte/chunked-body limits, ownership and scoped duplicate detection.
  PDF pages, image pixels, archive ratios and parser timeout/tree cleanup are tested.
- Parser/fallback logs exclude a sensitive exception marker. Large/disabled model inputs
  cannot construct a network provider; corrected fallback still preserves provenance.
- `tests/test_security_migrations.py` verifies fresh/repeated migration/model consistency,
  synthetic legacy content/path/hash preservation and quarantine, and rejection of an
  unknown legacy schema before adopting it. Real data was not opened or copied.
- Existing component tests explicitly inject a trusted synthetic principal. This is
  separate from real security tests; there is no production test-mode bypass.

## Browser evidence

The first browser journey signs in as an Employee, uploads a real TXT through the
production bridge and bounded parser, signs in as a Reviewer, records corrected fields,
approves a verified pending rule, downloads its actual synthetic DOCX source, returns as
Employee, evaluates both requirements, inspects quotations/review attribution and signs
out. A subsequent direct bridge request is 401. The second creates an account as Admin,
reloads to verify persistence, then signs out. Auth, CSRF, scopes and source verification
are real; policy/account fixtures are synthetic and model inference is disabled.

The captured [policy evidence page](screenshots/milestone-2-policy-evidence.png) was
visually inspected. Earlier browser runs exposed locator assumptions (CSS-capitalized
review labels and quotations containing a child rule ID); selectors were corrected.
The UI required-action object contract was also corrected before the successful journey.
No screenshots or passing results were fabricated.

## Material limitations / NOT RUN

- Remote GitHub Actions, Linux/Node 22/Chromium execution and a clean dependency install:
  **NOT RUN locally**. Their CI definitions were updated; no remote success is claimed.
- Python vulnerability scanning, container scans, penetration testing, load/SLO tests,
  actual deployment/TLS, backup/restore and PostgreSQL recovery: **NOT RUN**. These remain
  later gates. Zero npm findings is not an overall security certification.
- Real Gemini, retrieval/model quality, latency/cost benchmarks and actual OCR binary
  execution: **NOT RUN**. Parser timing/tree cleanup tests mock timeout paths; they do
  not prove OS sandboxing or aggregate memory isolation.
- Existing legacy resources/checkpoints are intentionally inaccessible until explicitly
  assigned/imported. There is no automatic ownership inference or migration rollback
  that deletes security data. Follow SECURITY.md and the root README on a new demo DB.
- Sessions/counters/audit are SQLite-backed; production proxy-aware throttling, retention,
  durable jobs, stronger isolation, SSO/account recovery and operational hardening remain.

Final review covered changed/new code, retained local/production guards, dependency
changes, authorization scope, migrations and credential-pattern exposure. It was not
an independent security audit or a repository-history secret scan.

## Milestone 2 requested product follow-up — 2026-10-30

Observed final checks on Windows, Python 3.12 and Node 24:

| Check | Observed result |
|---|---|
| Full `python -m pytest -q` | **261 passed in 112.60s** |
| Full `python -m ruff check . --no-cache` | Passed |
| Frontend `npm run lint` (`tsc --noEmit`) | Passed |
| Frontend `npm run build` | Passed; all existing routes plus `/users` retained |
| Production frontend Playwright, installed Edge | **3 passed in 31.7s** |
| `git diff --check` | Passed |

The build/browser runs used the existing isolated frontend verification directory,
with no secret environment files copied. SHA-256 comparison found zero differences
between built application source/configuration/manifests and workspace equivalents.
The ephemeral backend runs real auth/CSRF, migrations, parser, source verification and
rule review; only policy model generation is synthetic. Document inference remains disabled.
No live model quality or completeness claim is made.

Added tests cover automatic multi-rule extraction from one chunk, invalid provenance/
threshold rejection, malformed/oversized model output, whole-policy input budget,
concurrent-processing guard, safe retry and duplicate prevention; explicit batch approval
and all-or-nothing rollback for missing/unverified/reviewed/foreign-policy rules; scoped
names/stats; denied forged profile fields; same-organization administrator naming;
name resolution in new/legacy audits; current-password validation, attempt throttling,
cookie rotation and revocation of other sessions; anonymous and CSRF denials. Migration
tests additionally upgrade a security-revision database containing a synthetic account,
session and audit entry, preserving their hashes/references/history and initializing names.

The third browser journey uploads a synthetic TXT policy, receives two verified pending
rules automatically, confirms bulk approval, sees named attribution, updates its profile,
checks role-specific metrics, changes its password and logs in with the new password.
The existing upload/review/evidence journey and administrator account journey also pass.
The [profile and policy screenshot](screenshots/milestone-2-profile-policy-flow.png)
comes from that actual browser run and was visually inspected.

The user's database, uploaded private policy, secrets and current Gemini model selection
were not read or changed. No migration was run against real data, and no commit, push,
deployment, external account change or real Gemini request was performed. No dependencies
were added for this follow-up. Earlier NOT RUN and production limitations still apply;
request-driven extraction crash recovery remains milestone 3 work.

## Investigation availability correction — 2026-10-30

Diagnosis: the existing Next.js gateway returns 404 unless NODE_ENV is development
and EDI_ENABLE_DEV_AGENT_FRONTEND is true. A local `npm start` production build therefore
cannot run investigation; this is the handoff's retained guard, not a Gemini failure.
The UI had incorrectly advertised readiness in that mode.

The `/investigate` server page now passes a non-secret availability reason to its client
component. Production and unconfigured local frontends disable question/submission,
show the restriction and omit the ready state. Backend-disabled 404 responses have an
actionable client message. No agent endpoint guard, scope, cookie or token was weakened.
Root README documents both frontend/backend flags, shared private token, actual resource
IDs, Gemini configuration, localhost address and development startup.

Observed checks: full pytest **261 passed in 119.29s**; full Ruff, frontend TypeScript,
production build and `git diff --check` passed. Source/configuration hashes match the
isolated built frontend. Final production Edge run: **4 passed in 34.1s**, including a
regression proving disabled UI and direct gateway 404 even with the frontend development
flag and synthetic shared token supplied. `/investigate` is now dynamically rendered so
configuration is evaluated on the server, without exposing token values to the browser.

The first browser run had one 5-second assertion timeout while policy parsing was still
running alongside the backend suite. Its snapshot showed the upload still in progress.
That test now waits explicitly for the bounded upload/extraction HTTP response and checks
its status before asserting rules, rather than assuming parsing completes in 5 seconds.
The final complete browser suite passed. Live Gemini/development inference and remote CI
were NOT RUN; the user's runtime configuration, secrets and database were untouched.
No dependencies, schema changes, commit, push or deployment for this correction.

## Account-derived investigation scope — 2026-10-30

The manual ID environment setup documented in earlier checkpoints is superseded.
Authenticated account/organization permissions now supply investigation scope. The page
loads scoped document/policy APIs, displays filenames, selects defaults and sends the
selected pair with the question. Both IDs are rechecked against current permissions;
they only narrow agent access. Legacy ID variables are ignored. Production, loopback,
token, session/CSRF, explicit review and deterministic source checks are retained.

Observed final checks:

- Full pytest: **276 passed in 106.24s**.
- Full Ruff, frontend TypeScript, production build and `git diff --check`: passed.
- Playwright runner: **13 passed in 39.2s**: four browser journeys, eight gateway-handler
  checks and one complete gateway/real-backend integration journey.
- SHA-256 comparison: zero application source/build-configuration/manifest differences
  between the isolated built frontend and workspace source.

The new real-auth tests demonstrate a ready deterministic investigation with absent or
stale ID configuration, explicit/implicit scope, read-only tools, generic denial of
cross-user/org/unknown IDs before model construction, rejected permission injection and
partial selections, narrowed staff tool scope and ownership rechecks. Empty accounts get
an upload-oriented message. An initial test incorrectly expected the read-only agent to
persist a PolicyValidation; it was corrected to assert no write, without changing tools.

The complete integration test authenticates a Reviewer, uploads a synthetic policy and
approves its verified rules, authenticates an Employee, discovers scoped records, then
submits selections through the actual development gateway handler to the actual FastAPI
server. It runs inspect_document, get_policy_evidence and evaluate_document_policy with
a synthetic Gemini client and returns a ready, source-backed answer while excluding the
model draft. The ephemeral backend deliberately has stale ID variables to prove they no
longer block an account. Only model generation is substituted; auth/CSRF, gateway, scope,
source verification, tool dispatch and deterministic evaluation run normally.

The browser journeys still use a production frontend, where investigation is intentionally
disabled. A live development browser investigation and real Gemini quality/quota behavior
were NOT RUN. No real user data, secrets or configuration was read/modified; no migrations,
new dependencies, real inference, commits, pushes, deployment or milestone 3 implementation.

## Milestone 3 — durable persistence and Arabic foundations (2026-10-30)

Implemented on `feat/edi-durable-persistence`, preserving the earlier uncommitted
milestones and original handoff. No commit, push, deployment, user-data migration/import
or real inference was performed. Tests use isolated synthetic accounts/files/databases;
both pytest and the browser backend explicitly replace inherited data-root configuration.

### Observed checks

| Check | Observed result |
|---|---|
| Full backend `python -m pytest -q` | **296 passed, 8 skipped in 131.16s**; skips require the separate PostgreSQL cluster |
| Dedicated real PostgreSQL suite | **8 passed in 21.64s**, official PostgreSQL 17.11 portable binaries; isolated UTF-8 loopback cluster |
| Real process restart smoke | Passed: separate worker processed a synthetic original, exited, PostgreSQL stopped/restarted, and a new process reopened/resumed its persisted LangGraph checkpoint |
| Targeted durable-job/profile-policy regressions | **34 passed in 76.80s**, including SQLite writes during a waiting model call |
| Ruff / pip check | Passed; no broken installed requirements |
| Frontend TypeScript / production build | Passed in isolated verification directory; application source/config/manifests compared by SHA-256: **39 files, zero mismatches** |
| Playwright | **13 passed in 44.0s** on the final repeat: four browser journeys, eight gateway checks, one gateway-to-real-backend synthetic investigation |
| Official Compose CLI | Default and compact configurations passed with isolated dummy secrets and an empty env file; Compose v5.6.1, executable SHA-256 verified against the official release asset |
| CI/config/source review | Four CI jobs parsed; Dockerfile local COPY sources checked; shell init uses LF; `git diff --check` passed |
| Public source/docs credential-pattern scan | 166 selected source/test/script/doc files, zero flagged paths; private files/data excluded |

Queue coverage includes durable 202 intake, original/hash preservation, abandoned claim
recovery with a reopened engine, concurrent claims, stale-worker rollback fencing, final
attempt exhaustion, bounded redacted retries, explicit retry, disabled-account rechecks,
cross-owner/tenant denial and pending-only/deduplicated whole-policy extraction. Legacy
completed documents without jobs cannot be overwritten through the retry endpoint.
Policy model generation happens before business write locks; its output still passes
stored-source verification inside the fenced write transaction. A blocked synthetic model
proves a second SQLite connection can update an account before generation completes.

PostgreSQL tests exercise repeatable migrations/schema comparison, real auth/profile,
atomic rate-limit upserts, concurrent claims, Unicode processing, safe SQLite import with
integer sequence repair and checkpoint persistence/resume. Readiness returns 503 for a
missing PostgreSQL migration table without exposing SQL, and SQLite readiness covers
missing/outdated/current heads. Restart smoke seeds reviewed/approved fixtures explicitly;
it does not test reimbursement approval or bypass live API permissions. Browser journeys
separately exercise actual HTTP/session/CSRF upload, review and rule-approval paths.

Import tests prove read-only rehearsal/source hash preservation, IDs/tenant/password hash/
Unicode/job preservation, old-session exclusion, no overwrite and tamper refusal. The
absolute destination becomes the default runtime original prefix. Files and DB commits
are not a distributed transaction; a failed apply can leave newly copied unreferenced
files. No actual user backup was opened or imported.

Arabic checks use real bounded UTF-8 TXT and native DOCX parsing, Arabic names/filenames/
JSON through SQLite/PostgreSQL and import. Mocked OCR proves `eng+ara`, timeout and explicit
missing-pack behavior; it does **not** measure recognition accuracy. Evidence/text previews
use automatic direction. Arabic classifier/field extraction, scanned/native PDF/table
coverage and source-verified Arabic policy interpretation remain unaccepted requirements
for milestones 4–7; see [Arabic acceptance](ARABIC_SUPPORT.md).

### NOT RUN / remaining acceptance

- Docker image builds, actual Compose startup/health, compact runtime and container restart:
  **NOT RUN**, Docker Engine unavailable locally. Official config validation does not prove
  image/runtime compatibility. CI defines build/start/synthetic smoke/restart gates, but
  remote CI was not triggered or observed. M3 container acceptance remains outstanding.
- Clean Linux dependency installation, Linux/Node 22/Chromium execution and container
  resource usage: **NOT RUN locally**. Local frontend used Node 24.15.0 and installed Edge;
  runtime pins passed Windows installed-environment checks/dry-run resolution, not a clean
  cross-platform install. CI gates Linux installation and Node 22.
- Actual Arabic OCR/CER/WER, real Gemini quality/quota/cost, load/SLO testing, TLS/public
  deployment, production backups/restore/HA and horizontal checkpoint scaling: **NOT RUN**.

Reproduce with normal Ruff/pytest/frontend checks plus
`python scripts/verify_postgres_local.py --bin <official-postgres-bin-directory>` and
`python scripts/verify_compose.py [--compose <official-compose-executable>]`.
Where Docker Engine exists, use the isolated CI `containers` job or a fresh synthetic-only
Compose project; never run the smoke against valued data. Startup, backup/import and
rollback constraints are in [PERSISTENCE.md](PERSISTENCE.md). M4 is not authorized by this
checkpoint; stop for user review.

## Milestone 3 Docker acceptance closed — 2026-10-30

This continuation supersedes the earlier Docker-unavailable limitations. Docker Desktop
4.97.0 / Linux Engine 29.9.2 and Compose 5.6.1 were available through the new per-user
installation. This process's PATH was stale, so the runner received the executable path
explicitly; no system Docker settings were changed.

Observed verification used run `30c0a6d38b12`, separate
`edi-verify-30c0a6d38b12-default` / `edi-verify-30c0a6d38b12-compact` projects and named
volumes, generated opaque synthetic credentials, an empty env file and loopback port
51746. No native database, uploaded private file, user env or existing secret was opened
or migrated. Only image tags, secret paths, frontend port and its permitted origin were
overridden. Existing service definitions, limits, volumes and readiness were exercised.

| Check | Observed result |
|---|---|
| Backend clean Linux/Python 3.12 image build | Passed, pinned runtime installation and `pip check` |
| Frontend clean Linux/Node 22 image build | Passed, `npm ci`, `npm run lint`, `npm run build` and standalone runtime packaging; npm reported zero vulnerabilities |
| Default profile | Passed: fresh PostgreSQL, migrations, API/worker/frontend startup and health; separate worker processed the synthetic job |
| Compact profile | Passed: fresh PostgreSQL and migrations; embedded API worker processed the job; no worker service created |
| OCR runtime packs | Both profiles reported `ara`, `eng`, `osd`; this is pack availability, not an Arabic OCR accuracy benchmark |
| Workflow restart | Both profiles persisted the original/hash/job/checkpoint, stopped every service including PostgreSQL, restarted and resumed LangGraph to `requires_approval` after an explicit synthetic review fixture |
| Actual HTTP lifecycle | Both profiles authenticated through the production Next.js bridge, uploaded a distinct mixed Arabic/English TXT with CSRF, returned 202, processed it through the real worker, preserved source/original hashes and kept it human-review gated |
| Second full-service restart | Both profiles preserved the HTTP-uploaded document/original and authenticated session; original bytes matched exactly after restart |
| Frontend static assets | Compact profile served the production HTML and its referenced CSS asset successfully |
| Runtime restrictions | Inspected non-root `edi`/`node` users, read-only application roots and configured memory caps; frontend bound only `127.0.0.1:51746`, API/DB had no published ports |
| Cleanup | Both owned test projects stopped successfully; `docker ps` showed no running containers for either. Containers/volumes/images/build caches were retained; no prune/delete/reset commands ran |
| Config/CI | Both Compose configurations passed again; CI YAML parsed and now invokes the same isolated runner for both profiles; remote Actions still NOT RUN |
| Final regression gates | Full Ruff passed; pytest **296 passed, 8 skipped in 139.83s** (opt-in PostgreSQL suite needs a separately supplied cluster); frontend TypeScript/build passed in the clean Linux image; `git diff --check` passed |

The CLI workflow smoke creates explicit synthetic review/rule fixtures; it is not an
API permission bypass or a new production endpoint. HTTP intake separately uses normal
session/CSRF/ownership checks. No real model calls, expense approvals or payments occurred.
The runner keeps synthetic credentials outside output and passes the temporary HTTP
fixture password to its owned container via stdin, not a command-line argument.

Added `scripts/verify_containers.py`; frontend Docker builds now enforce TypeScript before
the production build. CI uses serial image builds to reduce pressure on small machines,
then checks both processing profiles independently. Reproduction/staged-run instructions
are in [PERSISTENCE.md](PERSISTENCE.md). Do not rerun completed profiles into their seeded
data; use a fresh run ID. Retained run files are ignored under `.local/container-verification`.

The earlier clean Linux install, Node 22 build and container runtime gaps are now closed.
Full Linux pytest/Chromium browser execution, sustained resource/load/SLO testing, actual
Arabic OCR/semantic accuracy, real Gemini quality/cost, public deployment/TLS and production
backup/restore/HA certification remain outside this observed checkpoint. Earlier Edge
Playwright results remain historical evidence; this continuation's container UI checks
use actual HTTP rather than a new browser run. Host free C: space after verification was
about 4.56 GiB; no user files or Docker data were deleted to make space.

### User-requested cleanup after the Docker run

After recording the results, the user explicitly requested removal of disposable run
artifacts. Removed the nine stopped verification containers, four synthetic volumes,
two verification networks and both `edi-verification-*` image tags for run
`30c0a6d38b12`. Kept the reusable PostgreSQL base image and Docker build cache. Project
source, documentation, handoff files, real databases/uploads, dependencies and frontend
builds were preserved. These removals supersede the retained-Docker-artifacts status above.

Automatic safety review rejected both the combined cleanup command and subsequent exact
recursive filesystem deletions, with only "blocked by policy" and no detailed reason.
The ignored `.local/container-verification/30c0a6d38b12` synthetic run files and root
`.pytest_cache`/`.ruff_cache` therefore remain. No alternative deletion mechanism was used.
