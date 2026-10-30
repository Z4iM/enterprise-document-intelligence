import os

import app.database.models  # noqa: F401
from alembic import context
from app.database.database import DATABASE_URL, Base, make_engine

config = context.config
target_metadata = Base.metadata
url = os.getenv("EDI_DATABASE_URL") or DATABASE_URL
if context.is_offline_mode():
    raise RuntimeError("Use an explicit database connection for checked migration.")
connection = config.attributes.get("connection")
if connection is not None:
    context.configure(
        connection=connection, target_metadata=target_metadata, compare_type=True
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = make_engine(url)
    with engine.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata, compare_type=True
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
