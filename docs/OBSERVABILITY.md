# Operational evidence and release gates — milestone 6

[NEXUS EDI](../README.md) · [Documentation guide](README.md)

## What changes in the application

Administrators get `/operations`: organization-only queue counts, failed/expired-lease
alerts, sampled operation latency/errors, reported model usage, optional configured cost
estimates and trace inspection. Employees/Reviewers cannot read its APIs; hiding the
navigation link is only a usability measure. Existing document/policy authority is unchanged.

`GET /operations/summary` reads at most 2,000 spans from the last 24 hours and 40 recent
spans; `GET /operations/traces/{id}` returns at most 128 spans, with truncation explicit.
Queue counts reflect current organization jobs, not a sampled counter. Unknown token/cost
values remain `null`/“Unknown”; zero is shown only when actually reported/calculated.
P50/P95 use nearest rank. These measurements are not load-test SLOs.

Every HTTP request gets a server-generated `X-Request-ID`. Caller correlation headers
are ignored. Trusted trace/parent IDs are stored with queued jobs, so attempts, model
requests, tool calls and LangGraph stages share lineage across processes. Status APIs
expose the opaque trace reference; it grants no access. The ordinary and development
gateways forward only validated references. Standard API error panels show the reference.

## Implementation and privacy

`app/observability/` implements local context-variable tracing with bounded typed spans,
JSON logging, token accounting, best-effort persistence and scoped diagnostic APIs. This
is comparable local tracing, not an installed OpenTelemetry SDK/exporter. No new runtime
service/dependency, broker, dashboard server or external telemetry upload was added.

The strict log formatter drops message text, arguments, tracebacks and arbitrary extras.
Only generated IDs, approved operation/status names, numeric measurements, timestamps,
levels and selected safe failure-type codes are emitted. It never logs prompts, outputs,
source quotations, filenames, query strings, cookies, credentials, emails or user IDs.
Independent third-party stdout/exporters are outside this formatter's control and need
review before deployment. No public metrics endpoint or tenant selector was added.

The request collector is shared safely across FastAPI thread-pool context copies;
worker collections are separate. Maximum 64 spans/collection; excess spans are dropped.
Database flush happens after the business transaction closes. Telemetry failures are
redacted and do not change business decisions. Stale attempts remain observable but
cannot publish workflow outcomes. Diagnostics are deliberately not audit authority.

Storage is a **soft cap of 20,000 spans/organization**. Concurrent flushes can overshoot
slightly. History is not automatically deleted; explicit retention/backup remains operator
work. The operations page reports caps/truncation. This is bounded diagnostic sampling,
not guaranteed billing accounting or complete distributed tracing. Anonymous/auth failures
have a log/header reference but no tenant database history. Operations reads do not
persist their own HTTP spans, avoiding self-generated dashboard traffic in aggregates.

Compose rotates JSON logs at 10 MB with three files/service. Native stdout retention
belongs to the operator. Format-specific parser imports keep TXT workers from loading
OCR/Office/PDF/model stacks; input, structure, output and deadline guards are unchanged.

`EDI_TELEMETRY_ENABLED=false` stops span recording/persistence; generated request references
and safe standard logs remain. Public examples contain names only, never real credentials.

## Tokens and cost

Gemini responses supply prompt, candidate, thought, cached, tool-prompt and total token
counters when available. Missing counters are not inferred as zero. Failed requests,
alternate HTTP providers and scripted responses may have no usage metadata. See
[provider field semantics](https://ai.google.dev/api/generate-content#UsageMetadata).

Cost estimation requires an exact configured model match and complete component counters:

```text
EDI_LLM_PRICING_MODEL=<exact requested model>
EDI_LLM_INPUT_USD_PER_MILLION=<operator-verified rate>
EDI_LLM_OUTPUT_USD_PER_MILLION=<operator-verified rate>
EDI_LLM_CACHED_INPUT_USD_PER_MILLION=<required when cache tokens are reported>
```

The formula prices uncached prompt + tool-prompt tokens at the input rate, cached prompt
at its configured rate and candidate + thought tokens at the output rate. Inconsistent
total/component counts, invalid rates or missing counters leave cost unknown. No current
provider prices are hard-coded. Tier differences, cache-write/storage, external tools,
unreported retries and billing adjustments are not covered. It is a configured linear
estimate for known sampled calls, **never an invoice or complete account spend**.

## Migration and rollback

Back up the business DB, originals and both checkpoint files; rehearse on a separate
copy, then use the same API/worker DB/root for `python -m alembic upgrade head`.
Head: `20261031_observability`. Adds nullable job trace/parent columns and
`telemetry_spans`; legacy jobs receive generated trace IDs when claimed. No real user
data was migrated during development. Downgrade refuses automatic history deletion;
restore a reviewed backup for rollback. Existing workflow/dev/CSRF/ownership guards stay.

## Reproduce evaluations and scans

```powershell
.\.venv\Scripts\python.exe evals/release/run.py --output-directory .local/release --ocr-report docs/benchmarks/bilingual-m6.json
# Intentionally fails while product-quality requirements remain unmet:
.\.venv\Scripts\python.exe evals/release/run.py --output-directory .local/release-quality --ocr-report docs/benchmarks/bilingual-m6.json --require-product-quality
```

The regression gate requires 20 native templates/language, exact supported field/
classification/policy goldens, source citation integrity, keyword baseline floors and
all fixed single-agent/specialist canonical outcomes. The separate product-quality gate
requires larger held-out scans, >=90% scan-field accuracy, >=90% retrieval abstention and
authorized live-model quality/cost evidence. These are initial engineering targets, not
statistical guarantees. Current template OCR and live-model coverage **do not pass**.
CI regression success must not be presented as product-quality certification.
Published M6 outputs are in [the release report bundle](benchmarks/release-m6/release.json).
The manifest hashes each report after CRLF-to-LF normalization, so Git line-ending
conversion does not invalidate Windows/Linux verification; other byte changes do.
The fresh [retrieval](benchmarks/retrieval-m6.json), [OCR](benchmarks/bilingual-m6.json)
and [security](benchmarks/security-m6.json) reports record their distinct measured scopes.

CI preserves JSON evaluation reports for seven days. It also runs pinned `pip-audit`
against runtime requirements without installation/resolution, npm's runtime advisory
audit, and checksum-pinned Grype against both built images. Dependency feeds need network
access; CI still performs no model inference or private-data upload. GitHub actions use
verified full commit SHAs. Scanner binaries install outside runtime images.

```powershell
python -m pip install -r requirements-security.txt # Prefer a separate tools environment
python -m pip_audit -r requirements-runtime.txt --no-deps --disable-pip --strict --format=json --output .local/python-vulnerabilities.json
python scripts/install_grype.py --directory D:/EDI-Storage/security-tools/grype-0.121.0
# With the built images available to Docker:
grype docker:edi-verification-backend:<run-id> --only-fixed --fail-on high -o json --file .local/backend-vulnerabilities.json
```

Grype's archive is pinned to official release SHA256 digests for Windows/Linux x86_64;
the installer refuses mismatched archives/binaries and extracts only the intended binary.
See [Grype installation](https://oss.anchore.com/docs/installation/grype/) and
[pip-audit](https://github.com/pypa/pip-audit). Image gating covers **fixable high/critical**
findings; lower/unfixed findings and scanner blind spots are not proof of safety. Runtime
Python audit and image scanning are complementary, not penetration tests.
The final frontend runtime removes the base image's global npm/npx tree; the
standalone server only needs `node`. This removes a separate toolchain dependency
surface that the application lockfile audit does not cover.

**On Windows, run the Linux scanner in Docker/WSL for Linux images.** Native Windows
Grype 0.121.0 can retain duplicate binary entries for Debian-owned files and report
upstream CVEs despite distribution backports. See [upstream issue #5466](https://github.com/anchore/syft/issues/5466).
The M6 cross-check uses the checksum-pinned Linux build, identical image archive,
identical current vulnerability database and identical severity/fixability flags;
no custom CVE/package ignore rules are added. Linux CI is the reference environment.
Debian Bookworm still has an unfixed util-linux partition-probing advisory
[CVE-2026-53615](https://security-tracker.debian.org/tracker/CVE-2026-53615);
`--only-fixed` is not an assertion that the image has no vulnerabilities. Retain
unfiltered scans and review vendor updates before any production decision.

## Resource-aware verification

On the observed 8 GB Windows host, run Python, browser/model checks and container builds
serially. Host commit exhaustion caused parser/authentication failures and a Docker CLI
cleanup failure; these cleared after idle Docker Desktop was stopped for native checks.
Only stop the engine after confirming no application containers are active, then restore
it for container verification. Preserve images/volumes; do not weaken password hashing,
parser budgets or review gates to accommodate concurrent verification workloads.

See [observed verification](VERIFICATION.md) for actual results. No live Gemini calls,
external publishing, deployment, production certification or automatic milestone 7 work
is authorized by implementing this milestone.
