from typing import List
from langchain_core.tools import tool
from db.parent_store_manager import ParentStoreManager
from qdrant_client.http import models as qmodels
from sentence_transformers import CrossEncoder
import config

class ToolFactory:
    _reranker: CrossEncoder | None = None  # shared across instances, loaded once

    def __init__(self, collection):
        self.collection = collection
        self.parent_store_manager = ParentStoreManager()
        self.state_filter = None
        if ToolFactory._reranker is None:
            print(f"Loading reranker model: {config.RERANKER_MODEL}")
            ToolFactory._reranker = CrossEncoder(config.RERANKER_MODEL)
            print("✓ Reranker loaded")

    def set_state_filter(self, state: str | None):
        """Set a namespace/state filter used for retrieval."""
        self.state_filter = state

    def _search_child_chunks(self, query: str, limit: int = 5, state: str | None = None) -> str:
        """Search for the top K most relevant child chunks.

        Args:
            query: Search query string
            limit: Maximum number of results to return (default 5, capped at 10).
            state: Optional state/namespace filter.
        """
        try:
            limit = max(1, min(limit, 10))  # guard against LLM passing extreme values
            qdrant_filter = None
            effective_state = state or self.state_filter
            if effective_state and effective_state.lower() not in ("all", "all states"):
                qdrant_filter = qmodels.Filter(
                    must=[qmodels.FieldCondition(
                        key="metadata.state",
                        match=qmodels.MatchValue(value=effective_state),
                    )]
                )

            # Over-fetch candidates for reranking
            fetch_k = limit * config.RERANKER_FETCH_MULTIPLIER
            candidates = self.collection.similarity_search(
                query,
                k=fetch_k,
                filter=qdrant_filter,
            )
            if not candidates:
                return "NO_RELEVANT_CHUNKS"

            # Rerank using cross-encoder then trim to requested limit
            pairs = [[query, doc.page_content] for doc in candidates]
            scores = ToolFactory._reranker.predict(pairs)
            ranked = sorted(zip(scores, candidates), key=lambda x: x[0], reverse=True)
            results = [doc for _, doc in ranked[:limit]]

            return "\n\n".join([
                f"Parent ID: {doc.metadata.get('parent_id', '')}\n"
                f"File Name: {doc.metadata.get('source', '')}\n"
                f"State: {doc.metadata.get('state', '')}\n"
                f"Content: {doc.page_content.strip()}"
                for doc in results
            ])

        except Exception as e:
            print(f"❌ search_child_chunks error: {e}")
            return f"RETRIEVAL_ERROR: {str(e)}"
    
    def _retrieve_many_parent_chunks(self, parent_ids: List[str]) -> str:
        """Retrieve full parent chunks by their IDs.
    
        Args:
            parent_ids: List of parent chunk IDs to retrieve
        """
        try:
            ids = [parent_ids] if isinstance(parent_ids, str) else list(parent_ids)
            raw_parents = self.parent_store_manager.load_content_many(ids)
            if not raw_parents:
                return "NO_PARENT_DOCUMENTS"

            return "\n\n".join([
                f"Parent ID: {doc.get('parent_id', 'n/a')}\n"
                f"File Name: {doc.get('metadata', {}).get('source', 'unknown')}\n"
                f"Content: {doc.get('content', '').strip()}"
                for doc in raw_parents
            ])            

        except Exception as e:
            return f"PARENT_RETRIEVAL_ERROR: {str(e)}"
    
    def _retrieve_parent_chunks(self, parent_id: str) -> str:
        """Retrieve full parent chunks by their IDs.
    
        Args:
            parent_id: Parent chunk ID to retrieve
        """
        try:
            parent = self.parent_store_manager.load_content(parent_id)
            if not parent:
                return "NO_PARENT_DOCUMENT"

            return (
                f"Parent ID: {parent.get('parent_id', 'n/a')}\n"
                f"File Name: {parent.get('metadata', {}).get('source', 'unknown')}\n"
                f"Content: {parent.get('content', '').strip()}"
            )          

        except Exception as e:
            return f"PARENT_RETRIEVAL_ERROR: {str(e)}"
    
    def create_tools(self) -> List:
        """Create and return the list of tools."""
        search_tool = tool("search_child_chunks")(self._search_child_chunks)
        retrieve_tool = tool("retrieve_parent_chunks")(self._retrieve_parent_chunks)
        retrieve_many_tool = tool("retrieve_parent_chunks_batch")(self._retrieve_many_parent_chunks)

        return [search_tool, retrieve_tool, retrieve_many_tool]