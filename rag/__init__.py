"""
rag/
----
Phase 7: RAG layer — Prompt Builder + Ollama Client + RAG Engine

Prompt Builder (Phase 7A):
    PromptBuilder, get_prompt_builder, build_prompt
    BuiltPrompt, PromptConfig, PromptTemplate
    ContextChunk, ConflictGroup, ConfidenceLabel, confidence_from_score

Ollama Client (Phase 7B):
    OllamaClient, OllamaConfig, get_ollama_client, reset_ollama_client
    OllamaError, OllamaConnectionError, OllamaTimeoutError,
    OllamaModelNotFoundError, OllamaResponseError

RAG Engine (Phase 7B):
    RAGEngine, RAGResponse, get_rag_engine, reset_rag_engine
"""

from rag.prompt_schema import (
    BuiltPrompt,
    ConfidenceLabel,
    ContextChunk,
    ConflictGroup,
    PromptConfig,
    PromptTemplate,
    confidence_from_score,
)
from rag.prompt_builder import (
    PromptBuilder,
    get_prompt_builder,
    build_prompt,
)
from rag.ollama_client import (
    OllamaClient,
    OllamaConfig,
    OllamaError,
    OllamaConnectionError,
    OllamaTimeoutError,
    OllamaModelNotFoundError,
    OllamaResponseError,
    get_ollama_client,
    reset_ollama_client,
)
from rag.rag_engine import (
    RAGEngine,
    RAGResponse,
    get_rag_engine,
    reset_rag_engine,
)
from rag.citation_schema import Citation, CitationList
from rag.citation_engine import (
    CitationEngine,
    get_citation_engine,
    reset_citation_engine,
)

__all__ = [
    # Prompt Builder
    "PromptBuilder", "get_prompt_builder", "build_prompt",
    "BuiltPrompt", "PromptConfig", "PromptTemplate",
    "ContextChunk", "ConflictGroup",
    "ConfidenceLabel", "confidence_from_score",
    # Ollama Client
    "OllamaClient", "OllamaConfig",
    "OllamaError", "OllamaConnectionError", "OllamaTimeoutError",
    "OllamaModelNotFoundError", "OllamaResponseError",
    "get_ollama_client", "reset_ollama_client",
    # RAG Engine
    "RAGEngine", "RAGResponse", "get_rag_engine", "reset_rag_engine",
    # Citation Engine
    "Citation", "CitationList",
    "CitationEngine", "get_citation_engine", "reset_citation_engine",
]
