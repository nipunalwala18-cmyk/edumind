"""
retrieval/
----------
Phase 6: Retrieval Engine

Exports:
    Retriever          — main retrieval class (use get_retriever() for singleton)
    get_retriever      — returns process-level singleton
    RetrievalQuery     — query specification model
    RetrievalResponse  — response model with results, citations, and stats
    RetrievalResult    — single ranked result
    RetrievalFilter    — optional metadata pre-filters
    SourceCitation     — source provenance model
"""

from retrieval.retrieval_schema import (
    RetrievalFilter,
    RetrievalQuery,
    RetrievalResponse,
    RetrievalResult,
    SourceCitation,
)
from retrieval.retriever import Retriever, get_retriever
from retrieval.bm25 import BM25Index, get_bm25_index
from retrieval.fusion import RecipRankFusion
from retrieval.reranker import CrossEncoderReranker, get_reranker

__all__ = [
    "Retriever", "get_retriever",
    "RetrievalQuery", "RetrievalResponse", "RetrievalResult",
    "RetrievalFilter", "SourceCitation",
    "BM25Index", "get_bm25_index",
    "RecipRankFusion",
    "CrossEncoderReranker", "get_reranker",
]
