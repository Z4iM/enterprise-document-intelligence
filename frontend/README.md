# EDI frontend

Existing Next.js App Router / React / TypeScript dashboard. Use Node 22 (CI).

```powershell
npm ci
npm run dev
```

Loopback `127.0.0.1:3000`; the allowlisted bridge forwards to FastAPI at
`http://127.0.0.1:8000` unless BACKEND_API_URL is supplied server-side. Follow the root
README to migrate a new local DB/bootstrap its administrator before sign-in. Do not
overwrite `.env.local` or put secrets in `NEXT_PUBLIC_*` variables.

SessionGate signs in through FastAPI, sends session-bound CSRF on writes and clears
query data on logout/expiration. Private business data is protected by backend role/
organization/ownership checks; page hiding is not the security boundary. The bridge
forwards session cookies/CSRF/origin, not client roles or arbitrary upstream URLs.

Routes: `/`, `/documents`, `/documents/[id]`, `/upload`, `/reviews`, `/policies`,
`/investigate`, `/workflows`, `/users`. Policies come from the scoped backend. Reviewers
correct fields and approve verified rules; admins create/disable organization accounts.
Policy uploads automatically extract all supported rules, with a confirmation before
bulk approval and individual decisions still available. Existing policies have a
whole-policy retry. Uploads return 202 with a saved original and durable background job;
document/policy screens poll processing state and offer retry for terminal failures.
Extracted text and quotations use automatic direction for Arabic/English content.
Arabic semantic extraction quality remains a later acceptance gate.
The user icon opens editable names, scoped activity by role,
password changes and logout; admins can name existing users as well.
The production investigation gateway intentionally remains 404. Workflow execution UI
is planned; existing backend APIs retain their local/token guards plus authentication.
The investigation page disables submission and explains production unavailability.
To run the existing agent, follow **Local AI investigation** in the root README and
use `npm run dev` at `127.0.0.1:3000` with both server-side flags, the shared private token,
backend Gemini configuration. Pick documents/policies by filename; account permissions
provide the scope automatically. Never bypass `NODE_ENV` guards.

```powershell
npm run lint
npm run build
$env:EDI_BROWSER_CHANNEL = 'msedge'
npm run test:e2e
```

`lint` is TypeScript, not ESLint. Playwright uses one worker, a production Next.js server,
loopback ports 3197/8197 and an ephemeral migrated backend. Installed Edge is the local
default; CI uses `EDI_BROWSER_CHANNEL=chromium` after `npx playwright install --with-deps
chromium`. It refuses to reuse an existing server. No personal credentials or real model
inference are required; only synthetic fixture accounts are created. Test artifacts are
ignored and traces are disabled to avoid credential-bearing request captures.

For local production-build testing, run `npm run build` then `npm start`. Back up and
migrate the backend's selected database to head before starting the updated backend;
the queue/profile migrations are explicit, never performed by frontend/backend startup.
Local HTTP uses backend `EDI_ENV=development`, independent of the Next.js build mode.

Styling remains Tailwind 4 through `@tailwindcss/postcss`. See root README and
`docs/SECURITY.md` for current limits and deployment caveats.

Milestone 5 adds `/workflows`: independent document/policy specialist traces, durable
pause/resume and explicit supporting-evidence review. Controls require `npm run dev`,
`EDI_ENABLE_DEV_WORKFLOWS_FRONTEND=true` and private `EDI_DEV_WORKFLOW_TOKEN`, matching
the backend's enabled workflow guard/token. Optional private loopback origin configuration
supports alternate local ports. The production gateway returns 404. Documentation
attestation is staff-only; employees see their scoped checklist. See
[`docs/SPECIALISTS.md`](../docs/SPECIALISTS.md) for setup, bounds and measured limitations.

The default browser run tests the production guard. A separate synthetic development
journey uses `EDI_E2E_WORKFLOW_DEV=true npx playwright test specialist-journey.spec.ts`
(PowerShell: set `$env:EDI_E2E_WORKFLOW_DEV='true'` first). Only generation is mocked;
real auth/CSRF, jobs, review, checkpoints and deterministic Arabic evaluation are exercised.

Milestone 6 adds the administrator-only `/operations` page: organization-scoped queue
health, sampled latency/errors, known token/pricing coverage and opaque trace lookup.
Employees/reviewers are denied by the backend as well as the UI. Normal production
builds can use this page with a valid admin session; investigation/workflow development
guards remain unchanged. Errors show a validated correlation reference when supplied
by the backend. Missing usage/cost stays Unknown. The backend database must explicitly
be migrated through `20261031_observability`; see [observability](../docs/OBSERVABILITY.md).
