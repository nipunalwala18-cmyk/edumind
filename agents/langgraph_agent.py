"""
agents/langgraph_agent.py
--------------------------
LangGraph agentic workflow for the VIT Institutional Knowledge Engine.

Workflow graph:
    START
      ↓
    router          — classify intent: RAG / greeting / out_of_scope
      ↓ (rag)
    retrieval       — run hybrid+rerank retrieval, collect context
      ↓
    validation      — check whether retrieved context is relevant
      ↓ (sufficient) ↓ (insufficient)
    answer          rewrite          ← rewrite query, retry retrieval once
      ↓               ↓
    reflection      answer
      ↓
    memory          ← persist turn to conversation memory
      ↓
    END

State schema:
    AgentState (TypedDict)
    - question, role: inputs
    - rewritten_query: produced by rewrite node
    - retrieval_response: from retrieval node
    - rag_result: from answer node (RAGPipelineResponse)
    - answer: final string answer
    - source_documents: list[str] for frontend
    - citations: list[dict] for frontend
    - confidence: str label
    - reflection_note: optional quality note
    - memory: list[dict] conversation turns
    - retry_count: prevents infinite rewrite loops
    - route: "rag" | "greeting" | "out_of_scope"
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any, Iterator, Optional, TypedDict

logger = logging.getLogger(__name__)

# Ensure project root on path
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class AgentState(TypedDict, total=False):
    question:           str
    role:               str
    rewritten_query:    str
    retrieval_response: Any          # RetrievalResponse
    rag_result:         Any          # RAGPipelineResponse
    answer:             str
    source_documents:   list[str]
    citations:          list[dict]
    confidence:         str
    confidence_score:   float
    retrieval_mode:     str
    processing_time_ms: float
    reflection_note:    str
    memory:             list[dict]   # [{"role":"user"|"assistant","content":str}]
    retry_count:        int
    route:              str          # "rag" | "greeting" | "out_of_scope"
    error:              str


# ---------------------------------------------------------------------------
# Node implementations
# ---------------------------------------------------------------------------

_GREETINGS = frozenset({
    "hi", "hello", "hey", "good morning", "good afternoon", "good evening",
    "howdy", "greetings", "what's up", "sup",
})

_OUT_OF_SCOPE_KEYWORDS = frozenset({
    "weather", "cricket", "football", "movie", "recipe", "joke",
    "stock price", "forex", "bitcoin", "politics",
})


def node_router(state: AgentState) -> AgentState:
    """Classifies the query to decide which path to follow."""
    q = state.get("question", "").lower().strip()

    if q in _GREETINGS or len(q.split()) <= 2 and any(g in q for g in _GREETINGS):
        return {**state, "route": "greeting"}

    if any(kw in q for kw in _OUT_OF_SCOPE_KEYWORDS):
        return {**state, "route": "out_of_scope"}

    return {**state, "route": "rag", "retry_count": state.get("retry_count", 0)}


def node_retrieval(state: AgentState) -> AgentState:
    """Runs hybrid+reranking retrieval on the current query."""
    query_text = state.get("rewritten_query") or state.get("question", "")
    role = state.get("role", "Public")

    try:
        from retrieval.retriever import get_retriever
        resp = get_retriever().retrieve_by_text(
            text=query_text,
            role=role,
            top_k=5,
            use_bm25=True,
            use_reranker=True,
        )
        return {**state, "retrieval_response": resp}
    except Exception as exc:
        logger.error("[AGENT] retrieval node failed: %s", exc)
        return {**state, "retrieval_response": None, "error": str(exc)}


def node_validation(state: AgentState) -> AgentState:
    """
    Checks whether retrieved results are sufficiently relevant.
    If the top result score is below threshold and we haven't retried, triggers rewrite.
    """
    resp = state.get("retrieval_response")
    retry_count = state.get("retry_count", 0)

    if resp is None or resp.total_results == 0:
        if retry_count < 1:
            return {**state, "route": "rewrite"}
        # Give up — let answer node handle empty results
        return {**state, "route": "answer"}

    top_score = resp.results[0].score if resp.results else 0.0
    if top_score < 0.35 and retry_count < 1:
        logger.info("[AGENT] validation: low top_score=%.3f, routing to rewrite", top_score)
        return {**state, "route": "rewrite"}

    return {**state, "route": "answer"}


def node_rewrite(state: AgentState) -> AgentState:
    """
    Rewrites the query to be more specific / keyword-focused.
    Uses simple heuristic rewrite (no LLM call to avoid latency).
    """
    question = state.get("question", "")
    # Strip question words and make it more noun-phrase focused
    rewrites = {
        "what is": "",
        "what are": "",
        "how do i": "procedure for",
        "how to": "procedure for",
        "can you explain": "",
        "tell me about": "",
        "describe": "",
        "explain": "",
    }
    q = question.lower()
    for src, dst in rewrites.items():
        q = q.replace(src, dst)
    q = q.strip(" ?.,")

    logger.info("[AGENT] rewrite: '%s' → '%s'", question[:60], q[:60])
    return {
        **state,
        "rewritten_query": q,
        "retry_count": state.get("retry_count", 0) + 1,
    }


def node_answer(state: AgentState) -> AgentState:
    """
    Runs the full RAG pipeline (prompt builder + Ollama + citation engine)
    using the already-retrieved context or re-running if needed.
    """
    question = state.get("question", "")
    role = state.get("role", "Public")

    # Handle non-RAG routes
    route = state.get("route", "rag")
    if route == "greeting":
        return {
            **state,
            "answer": f"Hello! I'm the VIT Institutional Knowledge Assistant. Ask me anything about VIT policies, procedures, academics, or operations.",
            "source_documents": [],
            "citations": [],
            "confidence": "HIGH",
            "confidence_score": 1.0,
        }
    if route == "out_of_scope":
        return {
            **state,
            "answer": "I'm specialised in VIT institutional knowledge. Please ask me about academics, policies, examinations, admissions, or administrative procedures.",
            "source_documents": [],
            "citations": [],
            "confidence": "HIGH",
            "confidence_score": 1.0,
        }

    # Full RAG pipeline run
    try:
        from rag_pipeline import get_pipeline
        pipeline = get_pipeline()
        resp = pipeline.run(question, role)

        source_docs = [c.display_name for c in resp.citations]
        citations = [
            {
                "display_name": c.display_name,
                "department":   c.department,
                "version":      c.version,
                "score":        round(c.score, 4),
                "chunk_index":  c.chunk_index,
                "total_chunks": c.total_chunks,
            }
            for c in resp.citations
        ]

        return {
            **state,
            "rag_result":         resp,
            "answer":             resp.answer,
            "source_documents":   source_docs,
            "citations":          citations,
            "confidence":         resp.confidence,
            "confidence_score":   round(resp.confidence_score, 4),
            "retrieval_mode":     resp.retrieval_mode,
            "processing_time_ms": round(resp.processing_time_ms, 1),
        }
    except Exception as exc:
        logger.error("[AGENT] answer node failed: %s", exc, exc_info=True)
        return {
            **state,
            "answer": "I encountered an error processing your request. Please try again.",
            "source_documents": [],
            "citations": [],
            "confidence": "UNKNOWN",
            "confidence_score": 0.0,
            "error": str(exc),
        }


def node_reflection(state: AgentState) -> AgentState:
    """
    Quality check on the generated answer.
    Adds a reflection_note if answer is suspiciously short or empty.
    """
    answer = state.get("answer", "")
    note = ""
    if not answer or len(answer) < 50:
        note = "Answer may be incomplete. The knowledge base may not have sufficient information for this query."
    elif state.get("confidence", "UNKNOWN") == "UNKNOWN":
        note = "Low confidence — consider rephrasing your question with more specific terms."
    return {**state, "reflection_note": note}


def node_memory(state: AgentState) -> AgentState:
    """Appends the current Q&A turn to conversation memory."""
    memory = list(state.get("memory", []))
    memory.append({"role": "user",      "content": state.get("question", "")})
    memory.append({"role": "assistant", "content": state.get("answer", "")})
    # Keep last 20 turns (10 Q&A pairs) to avoid unbounded growth
    if len(memory) > 20:
        memory = memory[-20:]
    return {**state, "memory": memory}


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def _build_graph():
    """Builds and compiles the LangGraph StateGraph."""
    try:
        from langgraph.graph import StateGraph, END
    except ImportError:
        raise ImportError(
            "langgraph is required. Run: pip install langgraph>=0.2.0"
        )

    g = StateGraph(AgentState)

    g.add_node("router",     node_router)
    g.add_node("retrieval",  node_retrieval)
    g.add_node("validation", node_validation)
    g.add_node("rewrite",    node_rewrite)
    g.add_node("answer",     node_answer)
    g.add_node("reflection", node_reflection)
    g.add_node("memory",     node_memory)

    g.set_entry_point("router")

    # Router → conditional
    g.add_conditional_edges(
        "router",
        lambda s: s.get("route", "rag"),
        {
            "rag":          "retrieval",
            "greeting":     "answer",
            "out_of_scope": "answer",
        },
    )

    g.add_edge("retrieval", "validation")

    # Validation → conditional
    g.add_conditional_edges(
        "validation",
        lambda s: s.get("route", "answer"),
        {
            "rewrite": "rewrite",
            "answer":  "answer",
        },
    )

    # Rewrite loops back to retrieval (once)
    g.add_edge("rewrite",    "retrieval")
    g.add_edge("answer",     "reflection")
    g.add_edge("reflection", "memory")
    g.add_edge("memory",     END)

    return g.compile()


# Lazy singleton
_compiled_graph = None


def get_agent():
    """Returns the compiled LangGraph agent (singleton)."""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = _build_graph()
    return _compiled_graph


def reset_agent():
    """Clears the singleton — for testing."""
    global _compiled_graph
    _compiled_graph = None


# ---------------------------------------------------------------------------
# Public run helper
# ---------------------------------------------------------------------------

def run_agent(question: str, role: str, memory: Optional[list] = None) -> dict:
    """
    Runs the LangGraph agent for a single query turn.

    Returns a dict compatible with the API response format.
    """
    initial_state: AgentState = {
        "question": question,
        "role":     role,
        "memory":   memory or [],
    }

    try:
        agent = get_agent()
        final_state = agent.invoke(initial_state)
    except Exception as exc:
        logger.error("[AGENT] run_agent failed: %s", exc, exc_info=True)
        return {
            "answer":             "Agent encountered an error. Please try again.",
            "source_documents":   [],
            "citations":          [],
            "confidence":         "0%",
            "confidence_score":   0.0,
            "retrieval_mode":     "agent_error",
            "processing_time_ms": 0.0,
            "reflection_note":    str(exc),
            "memory":             memory or [],
        }

    return {
        "answer":             final_state.get("answer", ""),
        "answer_with_refs":   final_state.get("answer", ""),
        "source_documents":   final_state.get("source_documents", []),
        "citations":          final_state.get("citations", []),
        "confidence":         final_state.get("confidence", "0%"),
        "confidence_score":   final_state.get("confidence_score", 0.0),
        "retrieval_mode":     final_state.get("retrieval_mode", "agent"),
        "processing_time_ms": final_state.get("processing_time_ms", 0.0),
        "reflection_note":    final_state.get("reflection_note", ""),
        "memory":             final_state.get("memory", []),
    }
