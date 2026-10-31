# NEXUS EDI local setup

Fresh environments, persistent storage and guarded development investigation. Run commands from the repository root unless stated otherwise.

## Run locally

### Docker Compose

Requirements: Docker Engine with Compose. The credential-generation helper uses Python;
Docker Desktop with its Linux backend is the locally verified Windows setup.

From the repository root, for a fresh local environment:

```powershell
python scripts/init_local_secrets.py
docker compose up --build
```

In a second terminal, bootstrap the first administrator **only for a fresh database**:

```powershell
docker compose exec api python -m app.auth.bootstrap --email admin@edi.test
```

Bootstrap prompts for your own 12–128 character password; there are no shipped login
credentials. Open [the dashboard](http://127.0.0.1:3000), sign in and create local Employee/
Reviewer accounts through **Users**. Only the frontend is published; API/DB stay private.
Named volumes retain records, originals and checkpoints across restarts.

Compose defaults to **disabled inference**: document processing uses review-gated fallback,
and automatic AI policy-rule extraction requires a separately configured provider.
The investigation gateway is intentionally unavailable in production frontend builds,
including Docker. Use native development below to exercise that agent.

The compact configuration runs the worker inside the API:

```powershell
docker compose -f compose.yaml -f compose.compact.yaml up --build
```

Normal/compact steady memory caps total approximately 1.9/1.4 GiB; workload requirements
remain unmeasured. Do not use `down --volumes` on valued data.
See [startup, persistence and safe import](PERSISTENCE.md).


### Native Windows development

Use Python **3.12** and Node **22**. Create a virtual environment only if absent, then:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-ci.txt
cd frontend
npm ci
cd ..
```

Choose a new demo database; keep the same environment for migration, bootstrap and server:

```powershell
$env:PYTHON_DOTENV_DISABLED = '1'
$env:EDI_ENV = 'development'
$env:EDI_DATABASE_URL = 'sqlite:///data/edi-demo.db'
$env:EDI_ALLOWED_ORIGINS = 'http://127.0.0.1:3000,http://127.0.0.1:8000'
$env:LLM_PROVIDER = 'disabled'
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m app.auth.bootstrap --email admin@edi.test
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In another terminal, run `npm run dev` from `frontend` and open
[127.0.0.1:3000](http://127.0.0.1:3000). The embedded worker starts with FastAPI.

For local HTTP login, the **backend terminal** must keep `EDI_ENV=development` and
the allowed loopback origins above, even when Next.js uses a production build. A 503
`Configure HTTPS application origins.` means the backend is requiring HTTPS; it does
not mean Next.js is offline. `/ready` returning `Database migrations required.` is a
separate issue: back up the configured database and migrate it using the same database
environment as the server. Do not change database URLs or bootstrap another account
as a workaround; an unsigned `/auth/me` returning 401 is expected.
OCR needs Tesseract with `eng` and `ara` packs; scanned PDFs also need Poppler on PATH.
TXT/native DOCX processing needs neither binary nor a GPU. Backend API documentation is
at [127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). `/health` is liveness; `/ready`
checks DB connectivity/migration head, not model quality.

Runtime pins are in `requirements-runtime.txt`; CI requirements add test tools.
`requirements.txt` additionally includes the heavier experimental retrieval stack.
The frontend uses `package-lock.json`. Variable names are documented in `.env.example`
and `frontend/.env.example`; preserve private configuration and never put credentials
in `NEXT_PUBLIC_*` variables.

### Local Gemini investigation

With a privately configured extraction provider, the normal UI supports policy upload,
pending rules, explicit approval and document review. Gemini investigation additionally
requires these **server-only** settings:

| Backend | Frontend development server |
|---|---|
| `EDI_ENABLE_DEV_AGENT=true` | `EDI_ENABLE_DEV_AGENT_FRONTEND=true` |
| `EDI_DEV_AGENT_TOKEN` — strong random shared secret | The same `EDI_DEV_AGENT_TOKEN` |
| Valid `GEMINI_API_KEY` and `GEMINI_MODEL` | No browser-exposed API key |

For Gemini-backed field/policy extraction, set backend `LLM_PROVIDER=gemini` with your
private provider configuration. The disabled-inference quick start cannot generate AI rules.

Restart the backend on loopback and use `npm run dev` at `http://127.0.0.1:3000`.
Select authorized documents/policies by filename; account permissions supply scope,
without manual ID environment lists. Official outcomes require explicitly reviewed fields
and verified, human-approved rules. Live requests consume provider quota; use synthetic
documents. Automated verification substitutes generation and makes no real LLM calls.

`npm run build` / `npm start` exercises the local production frontend; normal business
APIs work, but investigation remains disabled by its development guard. Local HTTP still
requires backend `EDI_ENV=development`. Do not override `NODE_ENV` or weaken the guards.
See [frontend/README.md](../frontend/README.md) for routes and account/profile behavior.



