"""Read-only source and no-overwrite import rehearsals; synthetic SQLite only."""

import hashlib
from datetime import timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database.database import Base
from app.database.import_sqlite import import_backup
from app.database.models import (
    AuthSession,
    Document,
    ProcessingJob,
    User,
    utc_now_naive,
)


@pytest.fixture
def backup(tmp_path):
    source = tmp_path / "source.db"
    engine = create_engine(f"sqlite:///{source.as_posix()}")
    target = create_engine(f"sqlite:///{(tmp_path / 'target.db').as_posix()}")
    Base.metadata.create_all(engine)
    Base.metadata.create_all(target)
    files = tmp_path / "backup-files"
    original = files / "uploads" / "doc" / "إيصال.txt"
    original.parent.mkdir(parents=True)
    original.write_text("إيصال ١٧٥", encoding="utf-8")
    with sessionmaker(bind=engine)() as db:
        db.add(
            User(
                id="user",
                email="synthetic@edi.test",
                organization_id="org",
                role="employee",
                display_name="مستخدم تجريبي",
                password_hash="synthetic-preserved-hash",
            )
        )
        db.add(
            Document(
                id="doc",
                organization_id="org",
                owner_id="user",
                original_filename=original.name,
                stored_file_path="old/reference",
                file_size_bytes=original.stat().st_size,
                file_hash=hashlib.sha256(original.read_bytes()).hexdigest(),
                structured_data={"name": "مطعم النيل"},
            )
        )
        db.add(
            AuthSession(
                token_hash="old-synthetic-token",
                user_id="user",
                csrf_hash="old-csrf",
                expires_at=utc_now_naive() + timedelta(hours=1),
                last_seen=utc_now_naive(),
            )
        )
        db.add(
            ProcessingJob(
                id="job",
                resource_id="doc",
                kind="document",
                actor_id="user",
                organization_id="org",
                state="running",
                attempts=1,
                lease_token="abandoned",
                lease_until=utc_now_naive(),
            )
        )
        db.commit()
    engine.dispose()
    try:
        yield source, files, tmp_path / "new-files", target
    finally:
        target.dispose()


def test_rehearsal_is_read_only_and_apply_preserves_unicode_ownership_and_job_ids(
    backup,
):
    source, files, destination, target = backup
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    assert not import_backup(source, files, destination, target)["applied"]
    assert not destination.exists()
    assert import_backup(source, files, destination, target, apply=True)["applied"]
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    with sessionmaker(bind=target)() as db:
        assert db.get(User, "user").password_hash == "synthetic-preserved-hash"
        assert db.get(User, "user").display_name == "مستخدم تجريبي"
        assert db.get(Document, "doc").owner_id == "user"
        assert db.get(Document, "doc").structured_data == {"name": "مطعم النيل"}
        imported_original = destination / "uploads" / "doc" / "إيصال.txt"
        assert db.get(Document, "doc").stored_file_path == imported_original.as_posix()
        assert imported_original.read_text(encoding="utf-8") == "إيصال ١٧٥"
        assert db.get(ProcessingJob, "job").state == "queued"
        assert db.get(ProcessingJob, "job").lease_token is None
        assert not db.scalars(select(AuthSession)).all()


def test_specialist_import_requires_matching_canonical_checkpoint_and_preserves_history(
    backup, tmp_path
):
    from langgraph.checkpoint.base import empty_checkpoint
    from langgraph.checkpoint.sqlite import SqliteSaver

    from app.database.models import (
        DocumentationReview,
        PolicyDocument,
        SpecialistWorkflow,
    )

    source, files, destination, target = backup
    original = files / "policies" / "policy" / "سياسة.txt"
    original.parent.mkdir(parents=True)
    original.write_text("سياسة تجريبية", encoding="utf-8")
    engine = create_engine(f"sqlite:///{source.as_posix()}")
    with sessionmaker(bind=engine)() as db:
        db.add(
            PolicyDocument(
                id="policy",
                organization_id="org",
                owner_id="user",
                original_filename=original.name,
                stored_file_path="old/policy",
                file_hash=hashlib.sha256(original.read_bytes()).hexdigest(),
            )
        )
        db.add(
            SpecialistWorkflow(
                id="workflow",
                organization_id="org",
                owner_id="user",
                document_id="doc",
                policy_id="policy",
                request_key="synthetic-import-key",
                question="Synthetic",
                checkpoint_thread="canonical-thread",
            )
        )
        for identifier in ("old-attestation", "new-attestation"):
            db.add(
                DocumentationReview(
                    id=identifier,
                    document_id="doc",
                    policy_id="policy",
                    rule_id="rule",
                    reviewer_id="user",
                    evidence_ids=["doc"],
                    source_digest=identifier,
                    note="Synthetic historic review",
                )
            )
        db.commit()
    engine.dispose()
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="checkpoint backup"):
        import_backup(source, files, destination, target)
    checkpoint = tmp_path / "specialists.sqlite"
    with SqliteSaver.from_conn_string(str(checkpoint)) as saver:
        saver.setup()
        with pytest.raises(ValueError, match="Missing canonical"):
            import_backup(
                source, files, destination, target, specialist_checkpoints=checkpoint
            )
        saver.put(
            {"configurable": {"thread_id": "canonical-thread", "checkpoint_ns": ""}},
            empty_checkpoint(),
            {},
            {},
        )
    assert import_backup(
        source,
        files,
        destination,
        target,
        specialist_checkpoints=checkpoint,
        apply=True,
    )["applied"]
    with sessionmaker(bind=target)() as db:
        assert (
            db.get(SpecialistWorkflow, "workflow").checkpoint_thread
            == "canonical-thread"
        )
        assert len(db.scalars(select(DocumentationReview)).all()) == 2
    assert (
        destination / "specialist_checkpoints.sqlite"
    ).read_bytes() == checkpoint.read_bytes()
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before


def test_existing_target_or_destination_cannot_be_overwritten(backup):
    source, files, destination, target = backup
    destination.mkdir()
    sentinel = destination / "keep.txt"
    sentinel.write_text("preserve", encoding="utf-8")
    with pytest.raises(ValueError, match="Destination"):
        import_backup(source, files, destination, target, apply=True)
    assert sentinel.read_text() == "preserve"
    with sessionmaker(bind=target)() as db:
        assert not db.scalars(select(User)).all()


def test_hash_mismatch_aborts_before_writing_target(backup):
    source, files, destination, target = backup
    (files / "uploads/doc/إيصال.txt").write_text("tampered synthetic", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        import_backup(source, files, destination, target, apply=True)
    assert not destination.exists()


def test_source_directory_cannot_be_the_destination(backup):
    source, files, _, target = backup
    with pytest.raises(ValueError, match="separate empty"):
        import_backup(source, files, files / "nested", target, apply=True)
