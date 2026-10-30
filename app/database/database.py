import os
from pathlib import Path

from sqlalchemy import URL, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_PATH = Path(os.getenv("EDI_DATA_ROOT", "data")) / "database.db"

DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)


def configured_url():
    url = os.getenv("EDI_DATABASE_URL")
    if url:
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    host = os.getenv("EDI_POSTGRES_HOST")
    if host:
        password_file = os.getenv("EDI_POSTGRES_PASSWORD_FILE")
        if not password_file:
            raise RuntimeError("PostgreSQL requires a mounted password secret.")
        return URL.create(
            "postgresql+psycopg",
            username="edi",
            password=Path(password_file).read_text().strip(),
            host=host,
            port=5432,
            database="edi",
        )
    return f"sqlite:///{DATABASE_PATH}"


DATABASE_URL = configured_url()


def make_engine(url):
    if isinstance(url, str):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    options = (
        {"check_same_thread": False, "timeout": 30}
        if str(url).startswith("sqlite")
        else {}
    )
    return create_engine(
        url, connect_args=options, pool_pre_ping=True, hide_parameters=True
    )


engine = make_engine(DATABASE_URL)


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def create_tables():
    Base.metadata.create_all(bind=engine)
