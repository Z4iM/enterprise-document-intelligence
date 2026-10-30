"""Explicit local bootstrap; never runs on startup and never ships passwords."""

import argparse
import getpass
import uuid

from sqlalchemy import select

from app.auth.api import passwords
from app.database.database import SessionLocal
from app.database.models import SecurityEvent, User


def main():
    parser = argparse.ArgumentParser(
        description="Create the first local EDI administrator after migrations."
    )
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    password = getpass.getpass("New administrator password (12–128 characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation or not 12 <= len(password) <= 128:
        raise SystemExit("Passwords must match and meet the length requirement.")
    with SessionLocal() as db:
        if db.scalar(select(User.id).limit(1)):
            raise SystemExit(
                "Bootstrap refused: accounts already exist. Use an authenticated administrator."
            )
        user = User(
            id=str(uuid.uuid4()),
            organization_id=str(uuid.uuid4()),
            email=args.email.strip().lower(),
            password_hash=passwords.hash(password),
            role="admin",
            active=True,
        )
        db.add(user)
        db.add(
            SecurityEvent(
                actor_id=user.id,
                organization_id=user.organization_id,
                action="bootstrap",
            )
        )
        db.commit()
    print(
        "Administrator created. Legacy documents remain quarantined; no ownership was inferred."
    )


if __name__ == "__main__":
    main()
