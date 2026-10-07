from sqlalchemy import select

from app.database.database import SessionLocal
from app.database.models import PolicyChunk

from app.rag.embeddings import EmbeddingService
from app.rag.vector_store import PolicyVectorStore


embedding_service = EmbeddingService()

vector_store = PolicyVectorStore()
vector_store.reset()

with SessionLocal() as db:

    statement = (
        select(PolicyChunk)
        .order_by(
            PolicyChunk.policy_id,
            PolicyChunk.chunk_index
        )
    )

    chunks = db.scalars(statement).all()


texts = [
    chunk.text
    for chunk in chunks
]


metadata = [
    {
        "chunk_id": chunk.id,
        "policy_id": chunk.policy_id,
        "chunk_index": chunk.chunk_index,
        "text": chunk.text
    }
    for chunk in chunks
]


embeddings = embedding_service.embed_texts(
    texts
)


vector_store.add(
    embeddings=embeddings,
    chunk_records=metadata
)


print(
    f"Indexed {len(chunks)} policy chunks."
)