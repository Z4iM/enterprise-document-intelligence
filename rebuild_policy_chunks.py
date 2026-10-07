from uuid import uuid4

from sqlalchemy import delete

from app.database.database import SessionLocal
from app.database.models import (
    PolicyDocument,
    PolicyChunk
)

from app.rag.chunking import chunk_text


POLICY_ID = "153b2620-111d-473e-991d-94b4734024b2"


with SessionLocal() as db:

    policy = db.get(
        PolicyDocument,
        POLICY_ID
    )

    if policy is None:
        raise ValueError(
            f"Policy not found: {POLICY_ID}"
        )

    # Generate new intelligent chunks
    chunks = chunk_text(
        policy.extracted_text
    )

    # Remove old fixed-size chunks
    db.execute(
        delete(PolicyChunk).where(
            PolicyChunk.policy_id == POLICY_ID
        )
    )

    # Store new chunks
    for index, chunk in enumerate(chunks):

        db.add(
            PolicyChunk(
                id=str(uuid4()),
                policy_id=POLICY_ID,
                chunk_index=index,
                text=chunk
            )
        )

    db.commit()


print(
    f"Rebuilt policy into {len(chunks)} section-aware chunks."
)

print("\nCHUNKS:\n")

for index, chunk in enumerate(chunks):

    print(
        f"\n--- CHUNK {index} ---"
    )

    print(
        chunk[:500]
    )