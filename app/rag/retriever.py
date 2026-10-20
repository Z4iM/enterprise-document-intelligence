from app.rag.embeddings import EmbeddingService
from app.rag.vector_store import PolicyVectorStore

embedding_service = EmbeddingService()
vector_store = PolicyVectorStore()


def retrieve_policy_context(
    query: str,
    top_k: int = 3
) -> list[dict]:

    query_embedding = embedding_service.embed_query(
        query
    )

    return vector_store.search(
        query_embedding=query_embedding,
        top_k=top_k
    )