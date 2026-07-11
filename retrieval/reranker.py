"""
retrieval/reranker.py
----------------------
Cross-encoder reranker using BAAI/bge-reranker-base.

Architecture:
    - Takes a query + N candidate chunks from RRF fusion (typically 25).
    - Scores each (query, chunk) pair with a BERT cross-encoder.
    - Returns the top-K chunks sorted by rerank score.

Why a cross-encoder after bi-encoder retrieval?
    Bi-encoder (BGE embedding): query and passage are encoded independently.
    Fast for retrieval (pre-compute passage embeddings), but less accurate
    because the query and passage never interact during encoding.

    Cross-encoder (bge-reranker-base): encodes the query and passage jointly.
    The full attention mechanism captures fine-grained query-passage interactions.
    Much more accurate, but cannot be pre-computed — only feasible on a small
    candidate pool (25 chunks × ~0.5s on CPU = acceptable latency).

Score normalization:
    CrossEncoder outputs raw logits (unbounded). We apply sigmoid to map
    to [0, 1]. Higher = more relevant.

Singleton pattern:
    bge-reranker-base is 278MB. Loaded once per process via get_reranker().
"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Optional

from retrieval.hybrid_search import RawSearchResult

logger = logging.getLogger(__name__)

RERANKER_MODEL = "BAAI/bge-reranker-base"


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_reranker_instance: Optional["CrossEncoderReranker"] = None


def get_reranker() -> "CrossEncoderReranker":
    """Returns the process-level CrossEncoderReranker singleton."""
    global _reranker_instance
    if _reranker_instance is None:
        _reranker_instance = CrossEncoderReranker()
        _reranker_instance.load()
    return _reranker_instance


# ---------------------------------------------------------------------------
# CrossEncoderReranker
# ---------------------------------------------------------------------------

class CrossEncoderReranker:
    """
    Cross-encoder reranker wrapping BAAI/bge-reranker-base.

    Public API:
        rerank(query, candidates, top_k) → list[RawSearchResult]
            - Returns top_k results sorted by rerank_score descending.
            - Each result has rerank_score set and score = rerank_score.
    """

    def __init__(self, model_name: str = RERANKER_MODEL) -> None:
        self._model_name = model_name
        self._model      = None
        self._device     = "cpu"

    def load(self) -> None:
        """Loads the cross-encoder model. Called once by the singleton factory."""
        import os
        disable_local = os.getenv("DISABLE_LOCAL_RERANKER", "false").lower() in ("true", "1", "yes")
        if disable_local:
            logger.info("[RERANKER] Local cross-encoder reranker is disabled via DISABLE_LOCAL_RERANKER.")
            self._model = None
            return

        try:
            from sentence_transformers import CrossEncoder
        except ImportError:
            raise ImportError(
                "sentence-transformers is required. Run: pip install sentence-transformers"
            )

        logger.info(f"[RERANKER] Loading {self._model_name} ...")
        self._model = CrossEncoder(
            self._model_name,
            max_length = 512,
            # apply_softmax=False — we apply sigmoid ourselves for [0,1] scores
        )
        logger.info(f"[RERANKER] {self._model_name} loaded.")

    def rerank(
        self,
        query:      str,
        candidates: list[RawSearchResult],
        top_k:      int,
    ) -> list[RawSearchResult]:
        """
        Score each (query, passage) pair and return top_k by rerank score.

        Args:
            query:      The preprocessed query string.
            candidates: RRF-fused candidates (typically 25).
            top_k:      Number of results to return after reranking.

        Returns:
            List of RawSearchResult with rerank_score populated, sorted
            by rerank_score descending, length = min(top_k, len(candidates)).
        """
        if self._model is None:
            # Reranker is disabled, return top search results directly
            return candidates[:top_k]

        self._assert_loaded()
        if not candidates:
            return []

        # Build input pairs: [(query, passage), ...]
        pairs = [(query, c.content) for c in candidates]

        # Score all pairs in one batch
        raw_scores = self._model.predict(pairs, show_progress_bar=False)

        # Sigmoid → [0, 1]
        import math
        def sigmoid(x: float) -> float:
            return 1.0 / (1.0 + math.exp(-float(x)))

        scored = [
            (candidate, sigmoid(float(score)))
            for candidate, score in zip(candidates, raw_scores)
        ]

        # Sort by rerank_score descending
        scored.sort(key=lambda x: x[1], reverse=True)

        results: list[RawSearchResult] = []
        for candidate, rr_score in scored[:top_k]:
            results.append(
                RawSearchResult(
                    chunk_id     = candidate.chunk_id,
                    content      = candidate.content,
                    score        = round(rr_score, 6),   # replace RRF score with rerank score
                    distance     = candidate.distance,
                    metadata     = candidate.metadata,
                    backend      = candidate.backend,
                    rerank_score = round(rr_score, 6),
                )
            )

        logger.debug(
            f"[RERANKER] Reranked {len(candidates)} → {len(results)} "
            f"(top score: {results[0].rerank_score:.4f})"
        )
        return results

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    @property
    def model_name(self) -> str:
        return self._model_name

    def _assert_loaded(self) -> None:
        if self._model is None:
            raise RuntimeError(
                "[RERANKER] Model not loaded. Call load() or use get_reranker()."
            )
