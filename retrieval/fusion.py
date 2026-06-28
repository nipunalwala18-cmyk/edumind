"""
retrieval/fusion.py
--------------------
Reciprocal Rank Fusion (RRF) over N ranked result lists.

RRF formula (Cormack et al. 2009):
    score(d) = Σ_lists  1 / (k + rank_list(d))

    k = 60  (standard constant — limits influence of very top-ranked docs,
             keeps contribution of lower-ranked docs meaningful)

Why RRF over weighted score combination?
    - Score scales differ wildly between backends: cosine similarity in [0,1]
      vs BM25 in [0, ~15]. Normalization is heuristic.
    - RRF only uses ranks, not scores — inherently robust to scale differences.
    - Empirically matches or beats weighted combination on most benchmarks
      (Cormack, Clarke, Buettcher 2009).

Documents appearing in multiple lists receive a contribution from each list,
so they accumulate higher fused scores — exactly the desired behavior for
documents that are both semantically similar AND keyword-matching.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Optional

from retrieval.hybrid_search import RawSearchResult

logger = logging.getLogger(__name__)

RRF_K = 60  # Standard constant. Literature range: 10–100; 60 is the default.


class RecipRankFusion:
    """
    Fuses N ranked lists of RawSearchResult into a single ranked list.

    Usage:
        fuser  = RecipRankFusion(k=60)
        fused  = fuser.fuse([dense_results, bm25_results], n_results=25)
    """

    def __init__(self, k: int = RRF_K) -> None:
        self._k = k

    def fuse(
        self,
        result_lists: list[list[RawSearchResult]],
        n_results: int,
    ) -> list[RawSearchResult]:
        """
        Merge multiple ranked lists into one via RRF.

        Args:
            result_lists: Each inner list is a ranked result list from one backend.
                          Lists may overlap (same chunk_id in multiple lists).
            n_results:    Maximum number of results in the fused output.

        Returns:
            Fused list sorted by RRF score descending, length ≤ n_results.
            The `score` field of each result holds the RRF score.
            The `backend` field is set to "hybrid".
        """
        if not result_lists:
            return []

        # Filter empty lists
        non_empty = [lst for lst in result_lists if lst]
        if not non_empty:
            return []
        if len(non_empty) == 1:
            # Only one active backend — return directly, no fusion overhead
            return non_empty[0][:n_results]

        # Accumulate RRF scores: chunk_id → cumulative RRF score
        rrf_scores: dict[str, float] = {}
        # Preserve best metadata + content per chunk (prefer dense over bm25)
        best_raw:   dict[str, RawSearchResult] = {}

        for result_list in non_empty:
            for rank, result in enumerate(result_list, start=1):
                contribution = 1.0 / (self._k + rank)
                cid = result.chunk_id
                rrf_scores[cid] = rrf_scores.get(cid, 0.0) + contribution
                # Keep the first-seen entry (dense list is passed first)
                if cid not in best_raw:
                    best_raw[cid] = result

        # Sort by RRF score descending, take top n_results
        top = sorted(rrf_scores.items(), key=lambda kv: kv[1], reverse=True)[:n_results]

        fused: list[RawSearchResult] = []
        for cid, rrf_score in top:
            original = best_raw[cid]
            fused.append(
                RawSearchResult(
                    chunk_id  = cid,
                    content   = original.content,
                    score     = round(rrf_score, 8),
                    distance  = original.distance,
                    metadata  = original.metadata,
                    backend   = "hybrid",
                    rerank_score = None,
                )
            )

        logger.debug(
            f"[RRF] Fused {sum(len(l) for l in non_empty)} candidates "
            f"from {len(non_empty)} lists → {len(fused)} results."
        )
        return fused

    @property
    def k(self) -> int:
        return self._k
