from app.rag.embeddings import EmbeddingService
from app.rag.vector_store import PolicyVectorStore

embedding_service = EmbeddingService()

vector_store = PolicyVectorStore()


query = """
An employee submitted a meal expense
of $175. Does this require approval?
"""


query_embedding = (
    embedding_service.embed_query(query)
)


results = vector_store.search(
    query_embedding=query_embedding,
    top_k=3
)


for position, result in enumerate(
    results,
    start=1
):
    print(
        f"\nRESULT {position}"
    )

    print(
        "Score:",
        round(
            result["similarity_score"],
            4
        )
    )

    print(
        "Chunk:",
        result["text"]
    )