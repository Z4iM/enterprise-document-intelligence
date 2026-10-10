from sqlalchemy import create_engine, inspect

# Import models so SQLAlchemy registers the tables
import app.database.models  # noqa: F401

from app.database.database import Base


def test_temporary_database_creation(tmp_path):
    # Pytest creates a temporary directory
    test_database_path = tmp_path / "test_database.db"

    # Create a separate SQLite engine
    test_engine = create_engine(
        f"sqlite:///{test_database_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )

    try:
        # Create tables in the TEST database only
        Base.metadata.create_all(bind=test_engine)

        # Inspect the newly created database
        inspector = inspect(test_engine)
        tables = inspector.get_table_names()

        # Verify that our important tables exist
        assert "documents" in tables
        assert "audit_events" in tables

        # Verify that the test database file was created
        assert test_database_path.exists()

    finally:
        test_engine.dispose()