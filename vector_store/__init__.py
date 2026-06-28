"""
vector_store/
-------------
Phase 5: ChromaDB Vector Store

Exports:
    ChromaStore      — persistent ChromaDB client wrapper with RBAC filtering
    run_indexing     — end-to-end Phase 4+5 orchestrator (embed → upsert → stamp)
"""

from vector_store.chroma_store import ChromaStore, get_chroma_store
from vector_store.index_pipeline import run_indexing

__all__ = ["ChromaStore", "get_chroma_store", "run_indexing"]
