"""
response_schema.py
------------------
Phase 9: Structured response schema for the integrated RAG pipeline.

Designed to be the stable contract between RAGPipeline (Phase 9) and
the future FastAPI layer (Phase 10) and LangGraph agents (Phase 11).

Dependency notes:
    - Imports ConfidenceLabel from rag.prompt_schema (pure enum, no I/O).
    - Imports Citation from rag.citation_schema (pure Pydantic model).
    - Does NOT import from rag_pipeline -- no circular dependency risk.
    - TYPE_CHECKING guard on RetrievalResult prevents runtime circular imports.

LangGraph note:
    RAGPipelineResponse can be serialized to/from JSON via .model_dump_json().
    Future LangGraph state graphs can pass it as a typed state field.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from pydantic import BaseModel, Field

from rag.prompt_schema import ConfidenceLabel
from rag.citation_schema import Citation

if TYPE_CHECKING:
    from retrieval.retrieval_schema import RetrievalResult


# ---------------------------------------------------------------------------
# Fallback answer
# ---------------------------------------------------------------------------

FALLBACK_ANSWER: str = (
    "I could not find sufficient institutional evidence to answer this question. "
    "The knowledge base may not contain information on this topic, or access may "
    "be restricted for your role."
)


# ---------------------------------------------------------------------------
# Confidence computation
# ---------------------------------------------------------------------------

def compute_confidence(
    results: "list[RetrievalResult]",
) -> tuple[ConfidenceLabel, float]:
    """
    Infers answer confidence purely from retrieval signals — no LLM call.

    Scoring rules:
        HIGH   : best_score >= 0.70  AND  at least 2 distinct supporting documents
        MEDIUM : best_score >= 0.40  OR   at least 2 distinct supporting documents
        LOW    : anything else
        UNKNOWN: no results

    Args:
        results: list[RetrievalResult] in rank order (index 0 = best).

    Returns:
        (ConfidenceLabel, effective_score_of_top_result)

    Both rerank_score and cosine-similarity score are sigmoid-normalized to
    [0, 1], so the same thresholds apply regardless of whether reranking ran.
    """
    if not results:
        return ConfidenceLabel.UNKNOWN, 0.0

    best = results[0]
    effective_score: float = (
        best.rerank_score
        if best.rerank_score is not None
        else best.score
    )
    n_unique_docs = len({r.citation.doc_id for r in results})

    if effective_score >= 0.70 and n_unique_docs >= 2:
        return ConfidenceLabel.HIGH, effective_score
    if effective_score >= 0.40 or n_unique_docs >= 2:
        return ConfidenceLabel.MEDIUM, effective_score
    return ConfidenceLabel.LOW, effective_score


# ---------------------------------------------------------------------------
# Sources block formatter
# ---------------------------------------------------------------------------

def format_sources_block(citations: list[Citation]) -> str:
    """
    Renders a numbered 'Sources' section from a CitationList.

    Format per line:
        N. <display_name> | <department> | v<version> | Page <page> | Chunk <n>/<total>

    Returns an empty string when citations is empty.
    """
    if not citations:
        return ""

    lines: list[str] = ["", "Sources:"]
    for c in citations:
        if c.total_chunks > 0:
            chunk_str = f"Chunk {c.chunk_index + 1}/{c.total_chunks}"
        else:
            chunk_str = f"Page {c.page_number}" if c.page_number > 0 else ""

        parts = [
            c.display_name,
            c.department,
            f"v{c.version}",
            f"Page {c.page_number}" if c.page_number > 0 else "",
            chunk_str,
        ]
        line = f"{c.rank}. " + " | ".join(p for p in parts if p)
        lines.append(line)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# RAGPipelineResponse
# ---------------------------------------------------------------------------

class RAGPipelineResponse(BaseModel):
    """
    The complete, structured output of a single RAGPipeline.run() call.

    Primary consumer contract — this is the object that:
        - Phase 9 tests validate
        - Phase 10 FastAPI serializes to JSON (via .model_dump_json())
        - Phase 11 LangGraph agents pass through their state graph

    Field groups:
        answer          — core LLM output in three forms
        citations       — deduplicated, ranked, formatted source references
        query meta      — echoed input fields
        timing          — per-phase latency measurements
        confidence      — retrieval-signal-based confidence estimate
        provenance      — model / template / retrieval mode labels
    """

    # --- Answer (three forms) ---
    answer: str = Field(
        ...,
        description="Raw LLM-generated answer, exactly as returned by Qwen3.",
    )
    answer_with_refs: str = Field(
        ...,
        description=(
            "Answer with [SOURCE N] placeholders replaced by [N] inline refs "
            "after citation deduplication and ranking."
        ),
    )
    formatted_answer: str = Field(
        ...,
        description=(
            "answer_with_refs followed by a formatted 'Sources:' block. "
            "This is the field shown to end users."
        ),
    )

    # --- Citations ---
    citations: list[Citation] = Field(
        default_factory=list,
        description="Deduplicated, ranked source citations from CitationEngine.",
    )
    retrieved_documents: int = Field(
        default=0,
        description="Number of unique documents in the retrieval result set.",
    )
    retrieved_chunks: int = Field(
        default=0,
        description="Total retrieved chunk count (before deduplication).",
    )

    # --- Query echo ---
    query: str = Field(..., description="Original user question.")
    role: str = Field(default="Public", description="RBAC role used for this query.")

    # --- Timing (all in milliseconds) ---
    processing_time_ms: float = Field(
        default=0.0,
        description="Wall-clock time for the complete pipeline (retrieval + LLM + citation).",
    )
    retrieval_time_ms: float = Field(
        default=0.0,
        description=(
            "Time for the retrieval phase (dense + BM25 + RRF + reranker). "
            "Reported by Retriever.latency_ms."
        ),
    )
    generation_time_ms: float = Field(
        default=0.0,
        description="Model eval time reported by Ollama (eval_duration / 1_000_000).",
    )
    total_tokens: int = Field(
        default=0,
        description="prompt_tokens + completion_tokens from Ollama.",
    )

    # --- Confidence ---
    confidence: ConfidenceLabel = Field(
        default=ConfidenceLabel.UNKNOWN,
        description=(
            "Retrieval-signal-based confidence: High / Medium / Low / Unknown. "
            "Never inferred from the LLM answer text."
        ),
    )
    confidence_score: float = Field(
        default=0.0,
        description="Effective score of the top retrieval result (rerank_score ?? score).",
    )

    # --- Provenance ---
    retrieval_mode: str = Field(
        default="unknown",
        description="'dense' | 'hybrid' | 'dense+rerank' | 'hybrid+rerank'",
    )
    model_name: str = Field(
        default="",
        description="Ollama model name that generated the answer.",
    )
    template_used: str = Field(
        default="default",
        description="PromptTemplate variant used.",
    )
    has_conflicts: bool = Field(
        default=False,
        description="True when version conflicts were detected in the retrieved context.",
    )
    chunks_in_context: int = Field(
        default=0,
        description="Number of chunks included in the LLM context window.",
    )

    # --- Metadata ---
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="UTC ISO-8601 timestamp of when this response was generated.",
    )

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    @property
    def is_fallback(self) -> bool:
        """True when the answer is the standard insufficient-evidence fallback."""
        return self.answer.startswith(
            "I could not find sufficient institutional evidence"
        )

    def short_summary(self) -> str:
        """One-line summary for logging / CLI output."""
        return (
            f"query={self.query[:50]!r} | "
            f"role={self.role} | "
            f"docs={self.retrieved_documents} | "
            f"confidence={self.confidence.value} | "
            f"tokens={self.total_tokens} | "
            f"latency={self.processing_time_ms:.0f}ms"
        )

    def to_display(self) -> str:
        """
        Human-readable multi-line summary for CLI / demo scripts.
        Suitable for verify_rag.py and demo.py output.
        """
        sep = "-" * 60
        lines = [
            sep,
            f"Query      : {self.query}",
            f"Role       : {self.role}",
            f"Mode       : {self.retrieval_mode}",
            f"Chunks     : {self.chunks_in_context} in context | "
            f"{self.retrieved_chunks} retrieved",
            f"Confidence : {self.confidence.value} (score={self.confidence_score:.4f})",
            f"Tokens     : {self.total_tokens}",
            f"Latency    : retrieval={self.retrieval_time_ms:.0f}ms  "
            f"generation={self.generation_time_ms:.0f}ms  "
            f"total={self.processing_time_ms:.0f}ms",
            sep,
            "Answer:",
            self.formatted_answer,
            sep,
        ]
        return "\n".join(lines)
