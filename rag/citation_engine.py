"""
rag/citation_engine.py
-----------------------
Phase 8: Source Citation Engine.

Pipeline:
    list[RetrievalResult] + answer str
        ↓  _group_by_doc()          — merge chunks from the same document
        ↓  _resolve_versions()      — flag superseded versions
        ↓  _sort()                  — score desc, then display_name asc (deterministic)
        ↓  _assign_ranks()          — 1-based rank + inline_ref "[N]"
        ↓  _inject_inline_refs()    — replace [SOURCE N] with [N] in answer text
    CitationList

Also supports ContextChunk input via build_from_chunks() for callers
that only have BuiltPrompt.context_chunks available (limited metadata).
"""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from typing import Optional, TYPE_CHECKING

from rag.citation_schema import Citation, CitationList

if TYPE_CHECKING:
    from retrieval.retrieval_schema import RetrievalResult
    from rag.prompt_schema import ContextChunk

logger = logging.getLogger(__name__)

# Matches [SOURCE 1], [SOURCE 12], [source 3] in generated answers
_SOURCE_RE = re.compile(r"\[SOURCE\s+(\d+)\]", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Version comparison (no external dependencies)
# ---------------------------------------------------------------------------

def _version_key(v: str) -> tuple:
    """Sortable key for version strings: '2.1' > '1.5' > '1.0' > 'Final' > ''."""
    nums = re.findall(r"\d+", v)
    return tuple(int(n) for n in nums) if nums else (0,)


# ---------------------------------------------------------------------------
# CitationEngine
# ---------------------------------------------------------------------------

class CitationEngine:
    """
    Stateless citation builder. Thread-safe — all state is local to build().

    Swap note: replace with a subclass or alternate implementation to change
    deduplication strategy without modifying any other module.
    """

    # ------------------------------------------------------------------
    # Primary API — accepts RetrievalResult (full metadata)
    # ------------------------------------------------------------------

    def build(
        self,
        results: "list[RetrievalResult]",
        answer:  str,
    ) -> CitationList:
        """
        Build a CitationList from retrieval results and the generated answer.

        Args:
            results: list[RetrievalResult] from Retriever.retrieve().
            answer:  Generated answer string from RAGEngine.generate().

        Returns:
            CitationList with sorted, deduplicated Citations and an
            annotated answer where [SOURCE N] → [N].
        """
        if not results:
            return CitationList(
                citations        = [],
                answer_with_refs = answer,
                original_answer  = answer,
                total_citations  = 0,
            )

        # 1. Merge chunks that belong to the same document
        groups = self._group_by_doc(results)

        # 2. Build a Citation per unique doc_id
        raw_citations = [
            self._build_citation_from_results(doc_id, doc_results)
            for doc_id, doc_results in groups.items()
        ]

        # 3. Flag superseded versions (same SOP, different version)
        raw_citations = self._resolve_versions(raw_citations)

        # 4. Sort: score desc, display_name asc for ties
        raw_citations = self._sort(raw_citations)

        # 5. Assign 1-based ranks and inline refs
        citations = self._assign_ranks(raw_citations)

        # Log each generated citation
        for c in citations:
            logger.info(
                f"[CITATION] [GEN] citation_id={c.citation_id} doc_id={c.doc_id} filepath={c.filepath}"
            )

        # 6. Build source_number → rank map for inline ref injection
        source_map = self._build_source_map(results, citations)

        # 7. Replace [SOURCE N] in answer
        answer_with_refs = _inject_inline_refs(answer, source_map)

        has_conflicts = any(not c.is_latest_version for c in citations)

        logger.debug(
            "[CITATION] %d results → %d citations | conflicts=%s",
            len(results), len(citations), has_conflicts,
        )

        return CitationList(
            citations             = citations,
            answer_with_refs      = answer_with_refs,
            original_answer       = answer,
            total_citations       = len(citations),
            has_version_conflicts = has_conflicts,
            source_number_map     = {str(k): v for k, v in source_map.items()},
        )

    # ------------------------------------------------------------------
    # Secondary API — accepts ContextChunk (limited metadata)
    # ------------------------------------------------------------------

    def build_from_chunks(
        self,
        chunks: "list[ContextChunk]",
        answer: str,
    ) -> CitationList:
        """
        Build CitationList from BuiltPrompt.context_chunks.

        Metadata available from ContextChunk is sufficient for most fields;
        source_file and access_level default to '' and 'Public' respectively.
        """
        if not chunks:
            return CitationList(
                citations        = [],
                answer_with_refs = answer,
                original_answer  = answer,
                total_citations  = 0,
            )

        # Group by doc_id (same dedup logic)
        groups: dict[str, list] = defaultdict(list)
        for chunk in chunks:
            groups[chunk.doc_id].append(chunk)

        raw_citations = [
            self._build_citation_from_chunks(doc_id, doc_chunks)
            for doc_id, doc_chunks in groups.items()
        ]

        raw_citations = self._resolve_versions(raw_citations)
        raw_citations = self._sort(raw_citations)
        citations     = self._assign_ranks(raw_citations)

        # source_number comes directly from ContextChunk.source_number
        source_map: dict[int, int] = {}
        for chunk in chunks:
            for c in citations:
                if chunk.doc_id == c.doc_id:
                    source_map[chunk.source_number] = c.rank
                    break

        answer_with_refs = _inject_inline_refs(answer, source_map)
        has_conflicts    = any(not c.is_latest_version for c in citations)

        return CitationList(
            citations             = citations,
            answer_with_refs      = answer_with_refs,
            original_answer       = answer,
            total_citations       = len(citations),
            has_version_conflicts = has_conflicts,
            source_number_map     = {str(k): v for k, v in source_map.items()},
        )

    # ------------------------------------------------------------------
    # Step 1: Group by doc_id
    # ------------------------------------------------------------------

    def _group_by_doc(
        self, results: "list[RetrievalResult]"
    ) -> dict[str, list]:
        groups: dict[str, list] = defaultdict(list)
        for r in results:
            groups[r.citation.doc_id].append(r)
        return dict(groups)

    # ------------------------------------------------------------------
    # Step 2a: Build Citation from RetrievalResult group
    # ------------------------------------------------------------------

    def _build_citation_from_results(
        self, doc_id: str, results: "list[RetrievalResult]"
    ) -> Citation:
        # Best result by effective score
        best = max(results, key=lambda r: (
            r.rerank_score if r.rerank_score is not None else r.score
        ))
        cit = best.citation

        # Earliest chunk in the document (lowest chunk_index)
        earliest = min(results, key=lambda r: r.citation.chunk_index)

        eff_score    = best.rerank_score if best.rerank_score is not None else best.score
        access_level = best.metadata.get("access_level", "Public")
        chunk_index  = earliest.citation.chunk_index
        
        filepath = best.metadata.get("source_file") or best.metadata.get("filepath") or ""

        return Citation(
            citation_id      = f"cite_{doc_id[:12]}",
            rank             = 0,   # assigned later
            inline_ref       = "",  # assigned later
            doc_id           = doc_id,
            display_name     = cit.display_name,
            title            = best.metadata.get("title") or cit.display_name,
            department       = cit.department,
            category         = cit.category,
            version          = cit.version,
            source_file      = cit.source_file,
            filepath         = filepath,
            section_heading  = best.citation.section_heading,
            chunk_ids        = [r.chunk_id for r in results],
            chunk_id         = best.chunk_id,
            chunk_index      = chunk_index,
            total_chunks     = cit.total_chunks,
            page_number      = chunk_index + 1 if chunk_index >= 0 else 0,
            score            = eff_score,
            rerank_score     = best.rerank_score,
            retrieval_score  = best.score,
            access_level     = access_level,
            is_latest_version = True,  # resolved later
        )

    # ------------------------------------------------------------------
    # Step 2b: Build Citation from ContextChunk group
    # ------------------------------------------------------------------

    def _build_citation_from_chunks(
        self, doc_id: str, chunks: "list[ContextChunk]"
    ) -> Citation:
        best = max(chunks, key=lambda c: (
            c.rerank_score if c.rerank_score is not None else c.score
        ))
        eff_score = best.rerank_score if best.rerank_score is not None else best.score

        # Best chunk_index: derive from rank (rank - 1 is a rough proxy)
        best_rank_chunk = min(chunks, key=lambda c: c.rank)
        chunk_index     = best_rank_chunk.rank - 1

        return Citation(
            citation_id      = f"cite_{doc_id[:12]}" if doc_id else f"cite_{id(best):x}",
            rank             = 0,
            inline_ref       = "",
            doc_id           = doc_id,
            display_name     = _extract_display_name(best.display_citation),
            title            = _extract_display_name(best.display_citation),
            department       = best.department,
            category         = best.category,
            version          = best.version,
            source_file      = "",
            filepath         = "",
            section_heading  = best.section_heading,
            chunk_ids        = [c.chunk_id for c in chunks],
            chunk_id         = best.chunk_id,
            chunk_index      = chunk_index,
            total_chunks     = 0,
            page_number      = chunk_index + 1,
            score            = eff_score,
            rerank_score     = best.rerank_score,
            retrieval_score  = best.score,
            access_level     = "Public",
            is_latest_version = True,
        )

    # ------------------------------------------------------------------
    # Step 3: Flag superseded versions
    # ------------------------------------------------------------------

    def _resolve_versions(self, citations: list[Citation]) -> list[Citation]:
        """
        Groups citations by (display_name, department, category).
        Within each group, marks all but the highest-version citation as
        is_latest_version=False.
        """
        # Group by identity key (ignoring version)
        groups: dict[tuple, list[Citation]] = defaultdict(list)
        for c in citations:
            key = (c.display_name.strip().lower(), c.department.strip().lower(), c.category.strip().lower())
            groups[key].append(c)

        result: list[Citation] = []
        for group in groups.values():
            if len(group) == 1:
                result.append(group[0])
                continue
            # Find the latest version
            latest = max(group, key=lambda c: _version_key(c.version))
            for c in group:
                is_latest = (c.doc_id == latest.doc_id)
                # model_copy creates a new instance with updated fields (Pydantic v2)
                result.append(c.model_copy(update={"is_latest_version": is_latest}))

        return result

    # ------------------------------------------------------------------
    # Step 4: Sort
    # ------------------------------------------------------------------

    def _sort(self, citations: list[Citation]) -> list[Citation]:
        """
        Deterministic sort:
            Primary  : effective score descending
            Secondary: display_name ascending (stable alphabetic tiebreak)
        """
        return sorted(
            citations,
            key=lambda c: (-c.score, c.display_name.lower()),
        )

    # ------------------------------------------------------------------
    # Step 5: Assign ranks and inline refs
    # ------------------------------------------------------------------

    def _assign_ranks(self, citations: list[Citation]) -> list[Citation]:
        ranked = []
        for i, c in enumerate(citations, start=1):
            ranked.append(c.model_copy(update={"rank": i, "inline_ref": f"[{i}]"}))
        return ranked

    # ------------------------------------------------------------------
    # Step 6: Build source_number → rank map
    # ------------------------------------------------------------------

    def _build_source_map(
        self,
        results:   "list[RetrievalResult]",
        citations: list[Citation],
    ) -> dict[int, int]:
        """
        Maps each original [SOURCE N] number (1-based, from the prompt) to
        the citation rank after merge + sort.
        """
        # doc_id → rank lookup
        doc_rank: dict[str, int] = {c.doc_id: c.rank for c in citations}

        source_map: dict[int, int] = {}
        for i, r in enumerate(results, start=1):
            doc_id = r.citation.doc_id
            if doc_id in doc_rank:
                source_map[i] = doc_rank[doc_id]

        return source_map


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def _inject_inline_refs(answer: str, source_map: dict[int, int]) -> str:
    """
    Replaces [SOURCE N] with [rank] in the answer text.
    Unknown source numbers are left as-is.
    """
    def _replace(m: re.Match) -> str:
        n    = int(m.group(1))
        rank = source_map.get(n)
        return f"[{rank}]" if rank is not None else m.group(0)

    return _SOURCE_RE.sub(_replace, answer)


def _extract_display_name(display_citation: str) -> str:
    """
    Extracts display_name from a display_citation string.
    e.g. 'Fee SOP (v2.0) — Section — chunk 1 of 10'  →  'Fee SOP'
    """
    # Strip " (vX.Y)" suffix
    s = re.sub(r"\s*\(v[^)]*\).*", "", display_citation).strip()
    return s or display_citation


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_engine_instance: Optional[CitationEngine] = None


def get_citation_engine() -> CitationEngine:
    """Returns the process-level CitationEngine singleton."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = CitationEngine()
    return _engine_instance


def reset_citation_engine() -> None:
    """Clears the singleton — for testing."""
    global _engine_instance
    _engine_instance = None
