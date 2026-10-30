"""Opt-in real PostgreSQL checks; only a dedicated local synthetic test cluster."""

import hashlib
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.auth.security import Principal, throttle
from app.database.database import Base, make_engine
from app.database.import_sqlite import import_backup
from app.database.models import AuditEvent, Document, ProcessingJob, User
from app.jobs.queue import claim, enqueue
from app.jobs.worker import run_once
from tests.test_security_migrations import migrate

pytestmark = pytest.mark.security


@pytest.fixture
def postgres():
    value = os.getenv("EDI_POSTGRES_TEST_URL")
    if not value:
        pytest.skip("Dedicated PostgreSQL test cluster not supplied.")
    url = make_url(value)
    if url.host not in {"127.0.0.1", "localhost"} or url.username not in {
        "ediverify",
        "edi_ci",
    }:
        raise ValueError(
            "Only the explicit isolated PostgreSQL test roles/loopback are accepted."
        )
    admin = make_engine(url).execution_options(isolation_level="AUTOCOMMIT")
    database = "edi_test_" + uuid.uuid4().hex
    with admin.connect() as connection:
        connection.exec_driver_sql(f"CREATE DATABASE \"{database}\" ENCODING 'UTF8'")
    engine = make_engine(url.set(database=database))
    try:
        migrate(engine)
        yield engine
    finally:
        engine.dispose()
        with admin.connect() as connection:
            connection.exec_driver_sql(f'DROP DATABASE "{database}" WITH (FORCE)')
        admin.dispose()


def test_real_postgres_migrations_repeat_and_match_models(postgres):
    migrate(postgres)
    with postgres.connect() as connection:
        assert (
            compare_metadata(MigrationContext.configure(connection), Base.metadata)
            == []
        )


def test_real_postgres_scoped_index_vectors_citations_and_removal(postgres):
    from app.database.models import PolicyDocument, PolicySearchIndex
    from app.jobs.queue import finish
    from app.rag.indexing import build_index, remove_index, request_index
    from app.rag.search import search_evidence
    from tests.test_authorized_retrieval import SyntheticEncoder, seed_index

    sessions = sessionmaker(bind=postgres, autoflush=False)
    encoder = SyntheticEncoder()
    seed_index(sessions, encoder=encoder)
    seed_index(
        sessions,
        identifier="foreign",
        organization="org-b",
        text="hidden-fixture-marker",
        encoder=encoder,
    )
    with sessions() as db:
        actor = Principal("pg-user", "org-a", "employee")
        result = search_evidence(db, actor, "موافقة المدير", encoder=encoder)
        assert result["mode"] == "hybrid"
        assert {hit["policy_id"] for hit in result["results"]} == {"search-policy"}
        assert result["results"][0]["source_verified"]
        remove_index(db, "search-policy")
        db.commit()
        assert (
            search_evidence(db, actor, "موافقة المدير", encoder=encoder)["status"]
            == "no_evidence"
        )
        request_index(
            db, "search-policy", Principal("reviewer", "org-a", "reviewer"), force=True
        )
        db.commit()
    identifier, token = claim(sessions)
    with sessions() as stale:
        job = stale.get(ProcessingJob, identifier)
        policy = stale.get(PolicyDocument, "search-policy")
        index = stale.get(PolicySearchIndex, policy.id)
        assert index.enabled
        with sessions() as other:
            remove_index(other, policy.id)
            other.commit()
        build_index(stale, policy, policy.extracted_text, encoder=encoder)
        with pytest.raises(RuntimeError, match="lease"):
            finish(stale, job, token)
    with sessions() as db:
        assert not db.get(PolicySearchIndex, "search-policy").enabled
        assert not search_evidence(db, actor, "موافقة المدير", encoder=encoder)[
            "results"
        ]


def test_real_postgres_readiness_handles_missing_migration_table(postgres, monkeypatch):
    from fastapi.testclient import TestClient

    from app import main

    monkeypatch.setattr(main, "SessionLocal", sessionmaker(bind=postgres))
    with TestClient(main.app, base_url="http://127.0.0.1:8000") as client:
        assert client.get("/ready").status_code == 200
        with postgres.begin() as connection:
            connection.exec_driver_sql("DROP TABLE alembic_version")
        response = client.get("/ready")
        assert response.status_code == 503
        assert "SELECT" not in response.text and "relation" not in response.text


def test_real_postgres_rate_limits_use_atomic_upsert(postgres):
    with sessionmaker(bind=postgres)() as db:
        throttle(db, "synthetic-counter", 2)
        throttle(db, "synthetic-counter", 2)
        with pytest.raises(HTTPException) as denied:
            throttle(db, "synthetic-counter", 2)
        assert denied.value.status_code == 429


def test_real_postgres_concurrent_workers_cannot_claim_same_job(postgres):
    sessions = sessionmaker(bind=postgres, autoflush=False)
    with sessions() as db:
        enqueue(
            db,
            "document",
            "synthetic-claim",
            Principal("synthetic-user", "synthetic-org", "employee"),
        )
        db.commit()
    with ThreadPoolExecutor(max_workers=2) as pool:
        leases = list(pool.map(lambda _: claim(sessions), range(2)))
    assert sum(lease is not None for lease in leases) == 1


def test_real_postgres_authentication_and_arabic_profile(postgres, monkeypatch):
    from fastapi.testclient import TestClient

    from app import main
    from app.auth.api import passwords

    sessions = sessionmaker(bind=postgres, autoflush=False)
    with sessions() as db:
        db.add(
            User(
                id="pg-auth",
                organization_id="pg-org",
                email="pg@synthetic.test",
                role="admin",
                password_hash=passwords.hash("synthetic-postgres-password"),
                display_name="مدير تجريبي",
                active=True,
            )
        )
        db.commit()
    monkeypatch.setattr(main, "SessionLocal", sessions)
    with TestClient(main.app, base_url="http://127.0.0.1:8000") as client:
        token = client.get("/auth/csrf").json()["csrf_token"]
        response = client.post(
            "/auth/login",
            json={
                "email": "pg@synthetic.test",
                "password": "synthetic-postgres-password",
            },
            headers={"x-csrf-token": token},
        )
        assert response.status_code == 200
        assert response.json()["user"]["display_name"] == "مدير تجريبي"
        assert client.get("/auth/profile").json()["stats"]["active_users"] == 1


def test_real_postgres_worker_and_workflow_checkpoint_resume(
    postgres, tmp_path, monkeypatch
):
    import threading

    from app.database.storage import file_storage, policy_storage
    from app.jobs.smoke import run_smoke
    from app.jobs.worker import serve
    from app.specialists.smoke import run_smoke as specialist_smoke
    from app.workflows import document_policy_graph

    sessions = sessionmaker(bind=postgres, autoflush=False)
    root = tmp_path / "durable-files"
    monkeypatch.setattr(file_storage, "UPLOAD_ROOT", root / "uploads")
    monkeypatch.setattr(policy_storage, "POLICY_ROOT", root / "policies")
    monkeypatch.setattr(document_policy_graph, "SessionLocal", sessions)
    monkeypatch.setenv("LLM_PROVIDER", "disabled")
    monkeypatch.setenv("EDI_ENABLE_DEV_WORKFLOWS", "true")
    monkeypatch.setenv("EDI_DATA_ROOT", str(root))
    stop = threading.Event()
    worker = threading.Thread(target=serve, args=(stop, sessions), daemon=True)
    worker.start()
    try:
        assert (
            run_smoke(sessions=sessions, root=root)["checkpoint"]
            == "waiting_for_review"
        )
        assert (
            specialist_smoke(sessions=sessions)["specialist_checkpoint"]
            == "waiting_for_review"
        )
    finally:
        stop.set()
        worker.join(timeout=10)
    # Reopening the SQLite saver with PostgreSQL-backed business records simulates app restart.
    assert (
        run_smoke(verify=True, sessions=sessions, root=root)["checkpoint"] == "resumed"
    )
    stop = threading.Event()
    worker = threading.Thread(target=serve, args=(stop, sessions), daemon=True)
    worker.start()
    try:
        assert (
            specialist_smoke(verify=True, sessions=sessions)["specialist_checkpoint"]
            == "resumed"
        )
    finally:
        stop.set()
        worker.join(timeout=10)


def test_real_postgres_durable_processing_preserves_arabic(
    postgres, tmp_path, monkeypatch
):
    from app.database.storage import file_storage
    from app.jobs import processors

    sessions = sessionmaker(bind=postgres, autoflush=False)
    root = tmp_path / "uploads"
    path = root / "pg-doc" / "إيصال.txt"
    path.parent.mkdir(parents=True)
    content = "Receipt\nإيصال من مطعم النيل\nTotal: $175.00"
    path.write_bytes(content.encode("utf-8"))
    monkeypatch.setattr(file_storage, "UPLOAD_ROOT", root)
    monkeypatch.setattr(
        processors,
        "extract_structured_data",
        lambda **kwargs: (
            {"merchant": "مطعم النيل", "total": "$175.00"},
            "regex_fallback",
            True,
        ),
    )
    with sessions() as db:
        db.add(
            User(
                id="pg-user",
                organization_id="pg-org",
                email="synthetic@edi.test",
                role="employee",
                active=True,
                password_hash="synthetic-unused-hash",
            )
        )
        db.add(
            Document(
                id="pg-doc",
                organization_id="pg-org",
                owner_id="pg-user",
                original_filename=path.name,
                stored_file_path=str(path),
                file_size_bytes=path.stat().st_size,
                file_hash=hashlib.sha256(path.read_bytes()).hexdigest(),
                processing_status="queued",
                review_status="processing",
            )
        )
        job = enqueue(
            db, "document", "pg-doc", Principal("pg-user", "pg-org", "employee")
        )
        identifier = job.id
        db.commit()
    assert run_once(sessions)
    assert not run_once(sessions)
    with sessions() as db:
        assert db.get(ProcessingJob, identifier).state == "completed"
        assert db.get(Document, "pg-doc").extracted_text == content
        assert db.get(Document, "pg-doc").structured_data["merchant"] == "مطعم النيل"


def test_sqlite_import_to_real_postgres_preserves_ids_hashes_names_and_sequences(
    postgres, tmp_path
):
    source = tmp_path / "backup.db"
    source_engine = create_engine(f"sqlite:///{source.as_posix()}")
    Base.metadata.create_all(source_engine)
    files = tmp_path / "backup-files"
    original = files / "uploads" / "import-doc" / "إيصال.txt"
    original.parent.mkdir(parents=True)
    original.write_text("إيصال تجريبي ١٧٥", encoding="utf-8")
    digest = hashlib.sha256(original.read_bytes()).hexdigest()
    with sessionmaker(bind=source_engine)() as db:
        db.add(
            User(
                id="import-user",
                organization_id="import-org",
                email="import@synthetic.test",
                display_name="مستخدم تجريبي",
                role="employee",
                active=True,
                password_hash="preserved-synthetic-hash",
            )
        )
        db.add(
            Document(
                id="import-doc",
                organization_id="import-org",
                owner_id="import-user",
                original_filename=original.name,
                stored_file_path="old-machine/reference",
                file_size_bytes=original.stat().st_size,
                file_hash=digest,
                structured_data={"merchant": "مطعم النيل"},
            )
        )
        db.add(
            AuditEvent(
                id=17,
                document_id="import-doc",
                event_type="synthetic",
                message="تم الرفع",
            )
        )
        db.commit()
    source_engine.dispose()
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    destination = tmp_path / "new-files"
    report = import_backup(source, files, destination, postgres)
    assert not report["applied"] and not destination.exists()
    report = import_backup(source, files, destination, postgres, apply=True)
    assert report["applied"]
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    assert (
        hashlib.sha256(
            (destination / "uploads/import-doc/إيصال.txt").read_bytes()
        ).hexdigest()
        == digest
    )
    with sessionmaker(bind=postgres)() as db:
        doc = db.get(Document, "import-doc")
        assert doc.owner_id == "import-user" and doc.organization_id == "import-org"
        assert doc.structured_data["merchant"] == "مطعم النيل"
        assert db.get(User, "import-user").password_hash == "preserved-synthetic-hash"
        event = AuditEvent(
            document_id=doc.id, event_type="after_import", message="حدث جديد"
        )
        db.add(event)
        db.commit()
        assert event.id == 18
