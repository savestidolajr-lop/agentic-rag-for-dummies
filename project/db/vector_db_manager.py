import config
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore, FastEmbedSparse, RetrievalMode
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

class VectorDbManager:
    __client: QdrantClient
    __dense_embeddings: HuggingFaceEmbeddings
    __sparse_embeddings: FastEmbedSparse

    def __init__(self):
        # Prefer connecting to a running Qdrant server (recommended for concurrency and stability).
        # If Qdrant isn't running, it will fall back to local embedded mode.
        try:
            kwargs = {"url": config.QDRANT_URL}
            if config.QDRANT_API_KEY:
                kwargs["api_key"] = config.QDRANT_API_KEY
            self.__client = QdrantClient(**kwargs)
            # Try a lightweight request to confirm connection
            self.__client.get_collections()
            collections = self.__client.get_collections()
            print(f"✅ Connected to Qdrant: {config.QDRANT_URL} ({len(collections.collections)} collections)")
        except Exception as e:
            # Fallback: use local (binary-based) mode via storage path
            print(f"⚠️  Qdrant remote connection failed ({e}), falling back to local storage.")
            self.__client = QdrantClient(path=config.QDRANT_DB_PATH)

        self.__dense_embeddings = HuggingFaceEmbeddings(model_name=config.DENSE_MODEL)
        self.__sparse_embeddings = FastEmbedSparse(model_name=config.SPARSE_MODEL)

    def _ensure_payload_indexes(self, collection_name):
        """Create payload indexes required for filtering. Safe to call if they already exist."""
        try:
            self.__client.create_payload_index(
                collection_name=collection_name,
                field_name="metadata.state",
                field_schema=qmodels.PayloadSchemaType.KEYWORD,
            )
        except Exception:
            pass  # Index already exists

    def create_collection(self, collection_name):
        if not self.__client.collection_exists(collection_name):
            print(f"Creating collection: {collection_name}...")
            self.__client.create_collection(
                collection_name=collection_name,
                vectors_config=qmodels.VectorParams(size=len(self.__dense_embeddings.embed_query("test")), distance=qmodels.Distance.COSINE),
                sparse_vectors_config={config.SPARSE_VECTOR_NAME: qmodels.SparseVectorParams()},
            )
            print(f"✓ Collection created: {collection_name}")
        else:
            count = self.__client.count(collection_name).count
            print(f"✓ Collection already exists: {collection_name} ({count} points)")
        self._ensure_payload_indexes(collection_name)

    def delete_collection(self, collection_name):
        try:
            if self.__client.collection_exists(collection_name):
                print(f"Removing existing Qdrant collection: {collection_name}")
                self.__client.delete_collection(collection_name)
        except Exception as e:
            print(f"Warning: could not delete collection {collection_name}: {e}")

    def delete_by_state(self, collection_name: str, state: str) -> int:
        """Delete all vectors whose metadata.state matches the given state. Returns deleted count."""
        try:
            result = self.__client.delete(
                collection_name=collection_name,
                points_selector=qmodels.FilterSelector(
                    filter=qmodels.Filter(
                        must=[qmodels.FieldCondition(
                            key="metadata.state",
                            match=qmodels.MatchValue(value=state),
                        )]
                    )
                ),
            )
            return result.status.value if hasattr(result, "status") else 0
        except Exception as e:
            print(f"Warning: could not delete vectors for state '{state}': {e}")
            return 0

    def count_by_state(self, collection_name: str, state: str) -> int:
        """Count vectors for a given state."""
        try:
            result = self.__client.count(
                collection_name=collection_name,
                count_filter=qmodels.Filter(
                    must=[qmodels.FieldCondition(
                        key="metadata.state",
                        match=qmodels.MatchValue(value=state),
                    )]
                ),
                exact=True,
            )
            return result.count
        except Exception:
            return 0

    def get_collection(self, collection_name) -> QdrantVectorStore:
        try:
            return QdrantVectorStore(
                    client=self.__client,
                    collection_name=collection_name,
                    embedding=self.__dense_embeddings,
                    sparse_embedding=self.__sparse_embeddings,
                    retrieval_mode=RetrievalMode.HYBRID,
                    sparse_vector_name=config.SPARSE_VECTOR_NAME
                )
        except Exception as e:
            print(f"Unable to get collection {collection_name}: {e}")