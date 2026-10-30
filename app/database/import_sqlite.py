"""Explicit rehearsal-first import of a backed-up, current-schema SQLite database."""

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
from datetime import UTC
from pathlib import Path, PureWindowsPath

from sqlalchemy import DateTime, Integer, create_engine, func, inspect, select, text

from app.database import models
from app.database.database import Base, make_engine

SKIP = {"auth_sessions", "request_limits"}


def import_backup(
    source,
    files_root,
    destination,
    target_engine,
    *,
    apply=False,
    stored_prefix=None,
    checkpoints=None,
):
    source, files_root, destination = (
        Path(source).resolve(),
        Path(files_root).resolve(),
        Path(destination).resolve(),
    )
    if (
        not source.is_file()
        or source == destination
        or destination.is_relative_to(files_root)
        or source.is_relative_to(destination)
    ):
        raise ValueError(
            "Use a backed-up SQLite file and a separate empty destination."
        )
    if source.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("Backup exceeds the 64 MiB import rehearsal limit.")
    if (
        target_engine.dialect.name == "sqlite"
        and Path(target_engine.url.database).resolve() == source
    ):
        raise ValueError("Target cannot be the source.")
    engine = create_engine(
        "sqlite://",
        creator=lambda: sqlite3.connect(source.as_uri() + "?mode=ro", uri=True),
    )
    try:
        schema = inspect(engine)
        for table in Base.metadata.sorted_tables:
            if table.name not in schema.get_table_names() or {
                c["name"] for c in schema.get_columns(table.name)
            } != set(table.c.keys()):
                raise ValueError(
                    "Source backup must be migrated to the current schema in a separate rehearsal copy."
                )
        rows, copies = {}, []
        with engine.connect() as connection:
            connection.exec_driver_sql("BEGIN")
            for table in Base.metadata.sorted_tables:
                if table.name not in SKIP:
                    rows[table.name] = [
                        dict(row)
                        for row in connection.execute(select(table)).mappings()
                    ]
                    for row in rows[table.name]:
                        for column in table.c:
                            if (
                                isinstance(column.type, DateTime)
                                and column.type.timezone
                                and row[column.name] is not None
                                and row[column.name].tzinfo is None
                            ):
                                row[column.name] = row[column.name].replace(tzinfo=UTC)
        if rows["workflow_runs"] and not checkpoints:
            raise ValueError("Workflow ownership requires its checkpoint backup.")
        if checkpoints:
            checkpoint = Path(checkpoints).resolve()
            with sqlite3.connect(
                checkpoint.as_uri() + "?mode=ro", uri=True
            ) as connection:
                if connection.execute("PRAGMA quick_check").fetchone() != ("ok",):
                    raise ValueError("Invalid checkpoint backup.")
            copies.append((checkpoint, destination / "langgraph_checkpoints.sqlite"))
        for row in rows["processing_jobs"]:
            if row["state"] in {"running", "retry_wait"}:
                row.update(
                    state="queued",
                    lease_token=None,
                    lease_until=None,
                    available_at=models.utc_now_naive(),
                )
        for table_name, folder in (
            ("documents", "uploads"),
            ("policy_documents", "policies"),
        ):
            for row in rows[table_name]:
                identifier, filename = row["id"], row["original_filename"]
                if (
                    not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", identifier)
                    or not filename
                    or filename in {".", ".."}
                    or PureWindowsPath(filename).name != filename
                    or "/" in filename
                ):
                    raise ValueError(
                        "Unsafe original reference; resolve it before import."
                    )
                relative = Path(folder) / identifier / filename
                original = (files_root / relative).resolve()
                if not original.is_relative_to(files_root) or not original.is_file():
                    raise ValueError("Original missing from the backup.")
                if original.stat().st_size > 20 * 1024 * 1024:
                    raise ValueError("Original exceeds the 20 MiB file budget.")
                with original.open("rb") as input_file:
                    digest = hashlib.file_digest(input_file, "sha256").hexdigest()
                if digest != row["file_hash"]:
                    raise ValueError("Original hash mismatch.")
                copies.append((original, destination / relative))
                prefix = Path(stored_prefix) if stored_prefix else destination
                row["stored_file_path"] = (prefix / relative).as_posix()
        with target_engine.begin() as target:
            for table in Base.metadata.sorted_tables:
                if target.scalar(select(func.count()).select_from(table)):
                    raise ValueError(
                        "Target must be migrated and empty; merging is not supported."
                    )
            if destination.exists() and any(destination.iterdir()):
                raise ValueError(
                    "Destination must be empty; originals are never overwritten."
                )
            if apply:
                for original, new_path in copies:
                    new_path.parent.mkdir(parents=True, exist_ok=True)
                    with (
                        new_path.open("xb") as output,
                        original.open("rb") as input_file,
                    ):
                        shutil.copyfileobj(input_file, output)
                for table in Base.metadata.sorted_tables:
                    if rows.get(table.name):
                        target.execute(table.insert(), rows[table.name])
                if target.dialect.name == "postgresql":
                    for table in Base.metadata.sorted_tables:
                        if "id" in table.c and isinstance(table.c.id.type, Integer):
                            # Table names come from trusted static metadata, never user input.
                            target.execute(
                                text(
                                    f"SELECT setval(pg_get_serial_sequence('{table.name}', 'id'), COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM {table.name}"
                                )
                            )
        return {
            "applied": apply,
            "tables": {name: len(items) for name, items in rows.items()},
            "originals_verified": len(copies),
            "sessions_imported": False,
            "jobs_preserved": True,
        }
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(
        description="Read-only rehearsal by default; never use live source data."
    )
    parser.add_argument("--source", required=True)
    parser.add_argument("--files-root", required=True)
    parser.add_argument("--destination", required=True)
    parser.add_argument(
        "--stored-prefix",
        help="Runtime file prefix; defaults to the absolute destination.",
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--checkpoints")
    args = parser.parse_args()
    from app.database.database import DATABASE_URL

    target = make_engine(DATABASE_URL)
    try:
        report = import_backup(
            args.source,
            args.files_root,
            args.destination,
            target,
            apply=args.apply,
            stored_prefix=args.stored_prefix,
            checkpoints=args.checkpoints,
        )
        print(json.dumps(report))
    except Exception as error:
        raise SystemExit(
            "Import refused; verify schema, empty target, original references and backup hashes. No source changes were made."
        ) from error
    finally:
        target.dispose()


if __name__ == "__main__":
    main()
