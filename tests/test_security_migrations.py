"""Fresh and synthetic legacy adoption; never open the developer database."""

from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext

from alembic import command
from app.database.database import Base
from app.database.models import utc_now_naive

pytestmark = pytest.mark.security


def migrate(engine):
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


def test_fresh_upgrade_is_repeatable_and_matches_models(tmp_path):
    engine = sa.create_engine(f"sqlite:///{(tmp_path / 'fresh.db').as_posix()}")
    try:
        migrate(engine)
        migrate(engine)
        with engine.connect() as connection:
            assert (
                compare_metadata(MigrationContext.configure(connection), Base.metadata)
                == []
            )
    finally:
        engine.dispose()


@pytest.mark.parametrize("revision", [None, "20261030_jobs", "20261030_retrieval"])
def test_readiness_requires_current_migration_without_exposing_db_errors(
    tmp_path, monkeypatch, revision
):
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker

    from app import main

    engine = sa.create_engine(f"sqlite:///{(tmp_path / 'readiness.db').as_posix()}")
    try:
        if revision:
            with engine.begin() as connection:
                connection.execute(
                    sa.text("CREATE TABLE alembic_version (version_num TEXT)")
                )
                connection.execute(
                    sa.text("INSERT INTO alembic_version VALUES (:revision)"),
                    {"revision": revision},
                )
        monkeypatch.setattr(main, "SessionLocal", sessionmaker(bind=engine))
        with TestClient(main.app, base_url="http://127.0.0.1:8000") as client:
            response = client.get("/ready")
            assert response.status_code == (200 if revision == "20261030_retrieval" else 503)
            assert "SELECT" not in response.text and "sqlite" not in response.text
            assert client.get("/health").status_code == 200
    finally:
        engine.dispose()


def test_legacy_rows_and_original_references_remain_quarantined(tmp_path):
    legacy = sa.MetaData()
    # Model table clones reconstruct the pre-security schema without mutating models.
    old_names = {
        "documents",
        "policy_documents",
        "policy_chunks",
        "policy_validations",
        "audit_events",
        "human_reviews",
        "stored_policy_rules",
        "policy_rule_reviews",
    }
    for name in old_names:
        table = Base.metadata.tables[name].to_metadata(legacy)
        for index in list(table.indexes):
            if any(
                column.name in {"organization_id", "owner_id"}
                for column in index.columns
            ):
                table.indexes.remove(index)
        for name in (
            "organization_id",
            "owner_id",
            "actor_id",
            "rule_extraction_status",
            "rule_extraction_message",
        ):
            if name in table.c:
                table._columns.remove(table.c[name])
    engine = sa.create_engine(f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}")
    legacy.create_all(engine)
    now = utc_now_naive()
    with engine.begin() as connection:
        connection.execute(
            legacy.tables["documents"]
            .insert()
            .values(
                id="legacy-synthetic",
                original_filename="synthetic.txt",
                stored_file_path="preserve/original.txt",
                file_size_bytes=99,
                file_hash="preserve-hash",
                processing_status="completed",
                review_status="approved",
                document_type="receipt",
                structured_data={"total": "$175.00"},
                structured_extraction_method="llm",
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            legacy.tables["policy_documents"]
            .insert()
            .values(
                id="legacy-policy",
                original_filename="synthetic.txt",
                stored_file_path="preserve/policy.txt",
                file_hash="policy-hash",
                created_at=now,
            )
        )
    try:
        migrate(engine)
        with engine.connect() as connection:
            row = (
                connection.execute(sa.text("SELECT * FROM documents")).mappings().one()
            )
            assert (
                row["organization_id"] == "legacy-unassigned"
                and row["owner_id"] is None
            )
            assert (
                row["stored_file_path"] == "preserve/original.txt"
                and row["file_hash"] == "preserve-hash"
            )
            assert "$175.00" in row["structured_data"]
            assert connection.scalar(sa.text("SELECT count(*) FROM users")) == 0
            assert (
                connection.scalar(sa.text("SELECT count(*) FROM policy_documents")) == 1
            )
    finally:
        engine.dispose()


def test_unrecognized_legacy_schema_is_refused_before_adoption(tmp_path):
    engine = sa.create_engine(f"sqlite:///{(tmp_path / 'unknown.db').as_posix()}")
    try:
        with engine.begin() as connection:
            connection.execute(sa.text("CREATE TABLE documents (id TEXT PRIMARY KEY)"))
        with pytest.raises(RuntimeError, match="Unsupported legacy schema"):
            migrate(engine)
        assert "users" not in sa.inspect(engine).get_table_names()
        assert [c["name"] for c in sa.inspect(engine).get_columns("documents")] == [
            "id"
        ]
    finally:
        engine.dispose()


def test_profile_upgrade_preserves_existing_account_session_and_audit(tmp_path):
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    engine = sa.create_engine(
        f"sqlite:///{(tmp_path / 'existing-security.db').as_posix()}"
    )
    try:
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "20261030_security")
            connection.execute(
                sa.text(
                    "INSERT INTO users (id, organization_id, email, password_hash, role, active) VALUES ('existing', 'org', 'fake@synthetic.test', 'preserve-hash', 'admin', 1)"
                )
            )
            connection.execute(
                sa.text(
                    "INSERT INTO auth_sessions (token_hash, user_id, csrf_hash, expires_at, last_seen) VALUES ('synthetic-token-hash', 'existing', 'synthetic-csrf-hash', '2026-10-31', '2026-10-30')"
                )
            )
            connection.execute(
                sa.text(
                    "INSERT INTO audit_events (document_id, event_type, message, created_at) VALUES ('doc', 'human_review', 'Document was approved by existing', '2026-10-30')"
                )
            )
        migrate(engine)
        with engine.connect() as connection:
            assert (
                connection.scalar(sa.text("SELECT password_hash FROM users"))
                == "preserve-hash"
            )
            assert connection.scalar(sa.text("SELECT display_name FROM users")) == ""
            assert (
                connection.scalar(sa.text("SELECT user_id FROM auth_sessions"))
                == "existing"
            )
            assert (
                connection.scalar(sa.text("SELECT message FROM audit_events"))
                == "Document was approved by existing"
            )
            assert (
                connection.scalar(sa.text("SELECT actor_id FROM audit_events")) is None
            )
    finally:
        engine.dispose()
