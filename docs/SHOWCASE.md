# Reproduce the NEXUS EDI showcase

[NEXUS EDI](../README.md) · [Documentation guide](README.md)

This local sandbox uses **synthetic data and scripted generation**. Sessions, CSRF,
ownership, source verification, rule decisions, document/evidence review, the queue,
specialist tools, checkpoints and deterministic evaluation are the actual application.
It does not measure Gemini quality or prove production readiness. Original development
guards stay enabled; production investigation/workflow gateways remain unavailable.

## Prepare an isolated public copy

Use Python 3.12, Git and Node 22. On Windows with limited C: space, choose a new directory
on D:. Run from the repository; the helper does not inspect project dotenv files.

```powershell
python scripts/prepare_showcase.py --directory D:/EDI-Storage/showcase/my-demo --install
```

The destination must not exist and must be outside the repository. The helper exports
tracked public working-source files and explicitly listed pending showcase materials,
records source hashes/base commit/dirty state, creates a fresh virtual environment and
runs pinned Python installation, `pip check` and `npm ci`. Downloads require internet;
the demonstration itself makes no inference API calls. Caches and temporary installation
files stay inside the selected destination. No services are started, data migrated or
existing directories overwritten. No reset/deletion command is provided.

An uncommitted source export is labeled as such; it is not a published Git release.
Use a clean reviewed checkout to rehearse the eventual published commit.
The helper filters paths, not arbitrary source content. Review source and existing Git
history before publishing; see the [legacy runtime-artifact release hold](SECURITY.md#m7-public-source-rehearsal-and-release-hold). Run heavy
checks serially on an 8 GB host. Docker and Playwright are optional additional tools.

## Start the synthetic sandbox

Terminal 1, from `D:/EDI-Storage/showcase/my-demo/source`:

```powershell
$env:PYTHON_DOTENV_DISABLED='1'
$env:PYTHONPATH=(Get-Location).Path
$env:EDI_E2E_WORKFLOW_DEV='true'
../venv/Scripts/python.exe tests/e2e_server.py --showcase-empty
```

Terminal 2, from that copy's `frontend` directory:

```powershell
$env:BACKEND_API_URL='http://127.0.0.1:8197'
$env:EDI_ENABLE_DEV_WORKFLOWS_FRONTEND='true'
$env:EDI_DEV_WORKFLOW_TOKEN='synthetic-browser-workflow-token'
$env:EDI_DEV_WORKFLOW_ORIGIN='http://127.0.0.1:3197'
$env:EDI_SHOWCASE_MODE='synthetic-scripted'
$env:NEXT_TELEMETRY_DISABLED='1'
npm run dev -- --hostname 127.0.0.1 --port 3197
```

Visit <http://127.0.0.1:3197>. This fixture server creates its own temporary database,
uploads and checkpoints, and **four synthetic accounts only**. It never uses your
application database. All fixture accounts use `synthetic-browser-password`:

| Email | Purpose |
|---|---|
| employee@synthetic.test | Upload the demonstration receipt and run its workflow |
| reviewer@synthetic.test | Upload/review policy rules, correct fields and attest evidence |
| colleague@synthetic.test | Demonstrate another employee cannot access the receipt |
| admin@synthetic.test | Inspect Operations and opaque trace references |

These credentials work only in the isolated test fixture, not normal EDI startup.
The visible banner must say **Synthetic demo / Scripted model generation**. Do not use
this server for real documents, expose either port publicly or present it as live AI.
Stop both terminals with Ctrl+C. The fixture's temporary state is removed when its
backend exits; restart persistence is verified separately below, not claimed for this
temporary server. Preserve any screenshots before stopping. For normal persistent
application setup and user-selected passwords, use the root README.

## Walk through the scenario

1. Reviewer uploads `docs/demo/fixtures/en-policy.txt` or `ar-policy.txt`. Inspect both
   source quotations, select **Approve all verified rules**, then explicitly confirm.
   Search the policy evidence and open the returned original; the default sandbox uses
   actual scoped keyword retrieval, not the optional semantic encoder.
2. Employee uploads the matching receipt TXT. Wait for processing, then start a workflow
   with that document/policy and ask what requirements apply. It pauses for field review.
3. Reviewer opens Review center and corrects merchant, total, category, ISO date and
   payment method against the original. Example totals: `175.50 USD` / `175.50 EGP`;
   category `meal` / `وجبات`; date `2026-10-31`; payment method `cash`.
4. In document details, choose the policy, open the original and explicitly confirm the
   receipt requirement with a review note. Field review does not approve the expense.
5. Employee resumes the workflow. Inspect both specialists, their scoped tool calls,
   original-language quotes and **requires approval** outcome. Documentation may be
   satisfied while manager approval is still required. Nothing approves reimbursement.
6. Inspect the document's Audit trail. As colleague, verify that the receipt/list/original
   are inaccessible. As admin, inspect Operations and a request's trace reference.

All fixtures are native UTF-8 text. OCR support has separate measured scan limitations;
this walkthrough does not demonstrate improved scan accuracy or universal policy parsing.

## Automated rehearsal and recovery

First stop any manual servers on 3197/8197. With Edge installed on Windows (CI installs
Chromium), from the sandbox frontend:

```powershell
$env:EDI_TEST_PYTHON='D:/EDI-Storage/showcase/my-demo/venv/Scripts/python.exe'
$env:EDI_E2E_WORKFLOW_DEV='true'
$env:EDI_E2E_SHOWCASE='true'
npx playwright test showcase.spec.ts
```

The runner refuses to reuse existing servers, starts fresh synthetic storage, exercises
both languages, checks cross-user denial, records reviewer/evidence actions and saves
screenshots in ignored `test-results`. Generation alone is scripted; no personal API key
is used. Other browser suites run with `EDI_E2E_SHOWCASE` unset.

For actual persistent service interruption/recovery, separately run the existing isolated
container runner. It uses owned fresh volumes/dummy secrets, not the temporary browser DB:

```powershell
python scripts/verify_containers.py
```

It builds/starts both profiles, pauses a specialist workflow, stops/restarts the services,
then reviews/resumes and checks persisted originals/sessions. No volumes are deleted.
An optional `--docker <executable>` handles Docker Desktop outside PATH. Do not conflate
that scripted integration proof with a recorded browser interaction or a load test.

Before public release, review the legacy history/data hold, choose an explicit repository
license (none is added by this milestone), and approve the reviewed commit and publication.
A finished video edit and public deployment are separate actions.

See [demo script](DEMO_SCRIPT.md), [portfolio claims](PORTFOLIO.md),
[verification](VERIFICATION.md) and [remaining quality gates](ARABIC_SUPPORT.md).
