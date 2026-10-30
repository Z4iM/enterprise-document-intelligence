# Local persistence, queue and import

## Native Windows/local startup

Use the same explicit `EDI_DATABASE_URL` and working directory for migration, bootstrap
and server. Back up valued data before upgrading. Migration `20261030_jobs` adds a new
queue table; it does not assign legacy ownership or change originals/accounts.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-runtime.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Default `EDI_PROCESSING_MODE=embedded` starts one worker with FastAPI. Uploads return
202 after validation and saving the original/resource/job. No additional local worker
command or copied resource IDs are needed. The UI polls scoped processing status and
offers explicit retry on terminal failure. `external` uses `python -m app.jobs.worker`;
`inline` retains the earlier synchronous API for component compatibility and is not the
durable processing path. Test fixtures select their mode explicitly.

`GET /health` is liveness. Public `GET /ready` checks DB connectivity and the expected
migration head without exposing configuration. `EDI_DATA_ROOT` defaults to `data` and
holds originals and SQLite LangGraph checkpoints; the business database can be PostgreSQL.

M5 head is `20261030_specialists`: workflow metadata and append-only evidence attestations.
The additional `specialist_checkpoints.sqlite` must be backed up with the business DB,
originals and existing `langgraph_checkpoints.sqlite`. Import of referenced specialist
threads requires `--specialist-checkpoints <backed-up-saver>`; missing threads fail the
read-only rehearsal. Upgrade only a separate rehearsal copy first. No real user database
was migrated as part of development. Per-lease checkpoint branches publish only through
the transactional queue fence; unpublished orphan retention remains future work.

Native OCR requires Tesseract with both `eng` and `ara` trained-data packs plus Poppler
for scanned PDFs. Check `tesseract --list-langs`. Missing packs fail explicitly; the
container definition installs both. `EDI_OCR_LANGUAGES=eng` is an English-only local
test option and does not satisfy Arabic acceptance.

## Compose startup (Docker required)

```powershell
.\.venv\Scripts\python.exe scripts/init_local_secrets.py
docker compose up --build
```

Open `http://127.0.0.1:3000`. For a fresh database only, create the administrator:

```powershell
docker compose exec api python -m app.auth.bootstrap --email admin@edi.test
```

The generator creates ignored local credential files without printing or overwriting
their values. The parent is mode 0700 on POSIX; Windows uses inherited NTFS permissions.
Read-only file mounts
allow non-root services to read their specific secret. PostgreSQL initializes a dedicated
`edi` login/database owner without superuser/create-role/create-database privileges.
No application passwords or API keys are baked into images. Compose defaults to disabled
inference and local HTTP cookies. Real Gemini use and public deployment remain separate.

Only frontend port 3000 is published, bound to loopback. API/DB/worker stay private.
The migration service must finish before API/worker startup. Named volumes preserve
PostgreSQL data, originals and checkpoints. Application containers are non-root with
read-only root filesystems, temporary parser storage, dropped capabilities and limits.
Default steady limits total about 1.9 GiB RAM and 3 CPU units; limits are caps, not measured
usage. A smaller process-count option is:

```powershell
docker compose -f compose.yaml -f compose.compact.yaml up --build
```

This embeds the worker in the API and omits the separate worker service. Do not use
`down --volumes` on valued data. Stopping/restarting without removing volumes preserves it.
Compose remains a single-host local setup, not a production TLS/backup/HA certification.
Current investigation/workflow development guards remain intact in production frontend builds.

## Job semantics and recovery

Jobs have unique kind/resource identity, three bounded attempts, exponential retry delay
and a 180-second claim lease. PostgreSQL workers use row locking/SKIP LOCKED; SQLite uses
a conditional atomic update. A crashed worker's lease can be reclaimed. Business changes
and the final lease-token fence commit together; a stale worker cannot commit its output.
Policy model calls finish before acquiring business write locks, so a slow model does
not hold SQLite's writer lock against account updates or upload/status requests.
This is at-least-once execution, not exactly-once model billing. A crash after a remote
request can incur another request on recovery; existing provider timeouts remain enforced.

Worker execution rechecks the active account, role, tenant/ownership, original path and
hash. Review/source verification remains mandatory. Rules are pending after extraction;
retry deduplication preserves existing approvals and avoids duplicate candidates. Failed
or queued resources cannot establish official policy outcomes. Only completed documents
appear in the field-review queue. Logs/status errors exclude provider messages/source text.

Shutdown stops new claims; interrupted work recovers after its lease. Parser/model limits
bound ordinary jobs, but OS/container memory exhaustion may terminate a process. Watch
job status rather than assuming an HTTP upload response means processing finished.

## Safe SQLite-to-PostgreSQL import

Stop writers and create consistent backups of the business DB, referenced originals and
checkpoint DB. **Never run rehearsal migration/import against the only copy or a live DB.**
Migrate a separate backed-up SQLite copy to head first. Prepare a fresh, empty migrated
PostgreSQL target; import before bootstrap, since imported accounts retain their password
hashes. Supply the target through `EDI_DATABASE_URL` in that terminal.

```powershell
python -m app.database.import_sqlite --source C:/EDI-backup/rehearsal.db --files-root C:/EDI-backup/data --destination C:/EDI-import/data --checkpoints C:/EDI-backup/data/langgraph_checkpoints.sqlite
```

Default is a read-only rehearsal: validate current schema, counts, safe references and
every original hash, with no target/file writes. `--apply` explicitly copies into an empty
destination and imports rows in a transaction. Use `--stored-prefix` to match the eventual
runtime data path (default: the absolute destination), and configure `EDI_DATA_ROOT`
consistently after import. For staged container imports, explicitly use `--stored-prefix data`
and copy the staged originals/checkpoints into the application's persistent data volume.
The source is opened read-only; IDs, account hashes, tenant ownership, audit, rules/reviews
and workflow ownership remain. Existing `legacy-unassigned` resources remain quarantined.
Checkpoint backup is required when workflow ownership rows exist. Imported running jobs
are requeued without old leases; attempts are retained. Sessions/request counters are not
imported, so users sign in again. PostgreSQL integer sequences are repaired after insertion;
timezone-aware historical timestamps are treated as UTC rather than target local time.

The tool refuses nonempty targets/destinations, bad hashes/references, incompatible schema,
backups over 64 MiB and originals over 20 MiB. It does not merge databases, infer ownership,
copy arbitrary stored file paths or erase anything. A failed apply rolls back DB inserts
but may leave newly copied files; rehearse using a new empty destination before retrying.
Rollback means restoring a reviewed backup and compatible code, not destructive downgrade.

## Verification commands

`python scripts/verify_compose.py` validates both profiles with isolated dummy secrets
and an empty env file; it never loads your `.env`. A standalone official Compose executable
can be supplied with `--compose`. Actual build/start checks require Docker Engine.

`python scripts/verify_postgres_local.py --bin <official-postgres-bin-directory>` creates
an ephemeral UTF-8 loopback cluster, runs real PostgreSQL tests, then runs a worker process,
stops/restarts PostgreSQL and verifies original/hash/job/checkpoint persistence and resume.
It does not install a system service or touch the project database. Container CI defines
the corresponding synthetic smoke and service restart checks, without personal API keys.

`python scripts/verify_containers.py` builds the two application images serially, then
tests the default and compact profiles separately with fresh synthetic databases/volumes.
It overrides only image tags, synthetic secret paths, the unused loopback frontend port
and its permitted origin; it never loads the user's `.env`, data or existing credentials.
It checks startup/migrations, OCR packs, worker processing, checkpoint resume, authenticated
HTTP upload, original integrity and session/data persistence after full-service restarts.
The compact run also checks the frontend HTML and its built CSS asset. CI uses this runner.

The runner stops its containers in `finally`; it does not delete containers, volumes,
images or build caches. Files/opaque synthetic credentials stay in ignored
`.local/container-verification/<run-id>` for inspection. An optional `--docker <executable>`
handles newly installed Docker not yet present on the calling process's PATH.
`--phase build|default|compact` with the same printed `--run-id` can split the run into
steps. Use a fresh run ID for a new complete rehearsal; completed profiles contain extra
HTTP-upload fixtures and are intentionally not reset or merged. Both profiles passed
locally on Docker Desktop's Linux engine; production readiness is still a separate gate.
