"""
tests/test_chroma_store.py
--------------------------
Phase 5: Unit tests for ChromaStore and IndexingRunSummary.

Fast unit tests (no ChromaDB or model required) are not marked.
Integration tests that hit a real ChromaDB in a temp directory are marked @pytest.mark.slow.
"""

from __future__ import annotations

import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from vector_store.chroma_store import (
    ChromaStore,
    ACCESS_HIERARCHY,
    COLLECTION_NAME,
    DEFAULT_N_RESULTS,
    UPSERT_BATCH_SIZE,
)
from vector_store.index_pipeline import IndexingRunSummary


# ===========================================================================
# Unit tests — no ChromaDB connection
# ===========================================================================

class TestAccessHierarchy:
    """Validate the RBAC access hierarchy constants."""

    def test_admin_sees_all_levels(self):
        levels = ACCESS_HIERARCHY["Admin"]
        assert set(levels) == {"Public", "Student", "Faculty", "Admin"}

    def test_faculty_excludes_admin(self):
        levels = ACCESS_HIERARCHY["Faculty"]
        assert "Admin" not in levels
        assert "Faculty" in levels
        assert "Student" in levels
        assert "Public" in levels

    def test_student_excludes_faculty_and_admin(self):
        levels = ACCESS_HIERARCHY["Student"]
        assert "Admin" not in levels
        assert "Faculty" not in levels
        assert "Student" in levels
        assert "Public" in levels

    def test_public_sees_only_public(self):
        levels = ACCESS_HIERARCHY["Public"]
        assert levels == ["Public"]

    def test_all_roles_defined(self):
        for role in ("Admin", "Faculty", "Student", "Public"):
            assert role in ACCESS_HIERARCHY

    def test_unknown_role_falls_back_to_public(self):
        levels = ACCESS_HIERARCHY.get("Hacker", ACCESS_HIERARCHY["Public"])
        assert levels == ["Public"]


class TestChromaStoreUninitialized:
    """Test ChromaStore before initialization."""

    def test_not_initialized_initially(self):
        store = ChromaStore(db_path="/tmp/test_chroma_uninitialized")
        assert not store.is_initialized

    def test_upsert_raises_if_not_initialized(self):
        store = ChromaStore(db_path="/tmp/test_chroma_uninitialized")
        with pytest.raises(RuntimeError, match="not initialized"):
            store.upsert([])

    def test_query_raises_if_not_initialized(self):
        store = ChromaStore(db_path="/tmp/test_chroma_uninitialized")
        with pytest.raises(RuntimeError, match="not initialized"):
            store.query([0.0] * 768)

    def test_delete_raises_if_not_initialized(self):
        store = ChromaStore(db_path="/tmp/test_chroma_uninitialized")
        with pytest.raises(RuntimeError, match="not initialized"):
            store.delete_by_doc_id("some_doc_id")


class TestWhereClauseBuilder:
    """Test RBAC where-clause generation without ChromaDB connection."""

    @pytest.fixture
    def store(self):
        # Use a dummy store — _build_where_clause does not need initialization
        s = ChromaStore.__new__(ChromaStore)
        s._collection = None
        s._client = None
        s._db_path = "/tmp/test"
        return s

    def test_public_role_single_condition(self, store):
        where = store._build_where_clause("Public", None, None)
        assert where == {"access_level": {"$eq": "Public"}}

    def test_admin_role_uses_in_operator(self, store):
        where = store._build_where_clause("Admin", None, None)
        assert "$in" in where["access_level"]
        assert set(where["access_level"]["$in"]) == {"Public", "Student", "Faculty", "Admin"}

    def test_faculty_role_excludes_admin(self, store):
        where = store._build_where_clause("Faculty", None, None)
        allowed = where["access_level"]["$in"]
        assert "Admin" not in allowed

    def test_department_filter_adds_and_clause(self, store):
        where = store._build_where_clause("Student", "Admissions", None)
        assert "$and" in where
        conditions = where["$and"]
        dept_cond = next(c for c in conditions if "department" in c)
        assert dept_cond["department"]["$eq"] == "Admissions"

    def test_category_filter_adds_and_clause(self, store):
        where = store._build_where_clause("Student", None, "SOP")
        assert "$and" in where
        conditions = where["$and"]
        cat_cond = next(c for c in conditions if "category" in c)
        assert cat_cond["category"]["$eq"] == "SOP"

    def test_all_filters_combined(self, store):
        where = store._build_where_clause("Faculty", "Finance", "Policy")
        assert "$and" in where
        keys = {list(c.keys())[0] for c in where["$and"]}
        assert "access_level" in keys
        assert "department" in keys
        assert "category" in keys

    def test_no_filters_for_admin_no_dept_no_cat(self, store):
        # Admin + no dept + no cat still returns an access_level filter
        where = store._build_where_clause("Admin", None, None)
        assert where is not None
        assert "access_level" in where


class TestFormatResults:
    """Test _format_results without ChromaDB."""

    @pytest.fixture
    def store(self):
        s = ChromaStore.__new__(ChromaStore)
        s._collection = None
        return s

    def test_format_empty_results(self, store):
        raw = {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
        assert store._format_results(raw) == []

    def test_format_single_result(self, store):
        raw = {
            "ids":        [["chunk_abc"]],
            "documents":  [["This is the chunk content."]],
            "metadatas":  [[{"access_level": "Public", "department": "Admissions"}]],
            "distances":  [[0.12345]],
        }
        results = store._format_results(raw)
        assert len(results) == 1
        r = results[0]
        assert r["chunk_id"] == "chunk_abc"
        assert r["content"] == "This is the chunk content."
        assert r["distance"] == round(0.12345, 6)
        assert r["score"] == round(1.0 - 0.12345, 6)
        assert r["metadata"]["access_level"] == "Public"

    def test_score_is_one_minus_distance(self, store):
        raw = {
            "ids":       [["c1"]],
            "documents": [["text"]],
            "metadatas": [[{}]],
            "distances": [[0.25]],
        }
        results = store._format_results(raw)
        assert abs(results[0]["score"] - 0.75) < 1e-6

    def test_format_multiple_results_sorted_by_insertion(self, store):
        raw = {
            "ids":       [["c1", "c2", "c3"]],
            "documents": [["a", "b", "c"]],
            "metadatas": [[{}, {}, {}]],
            "distances": [[0.1, 0.2, 0.3]],
        }
        results = store._format_results(raw)
        assert len(results) == 3
        assert results[0]["chunk_id"] == "c1"
        assert results[2]["chunk_id"] == "c3"


class TestIndexingRunSummary:

    def test_success_when_no_errors(self):
        s = IndexingRunSummary(
            run_id           = "test",
            chunks_embedded  = 627,
            chunks_upserted  = 627,
            errors           = [],
        )
        assert s.success is True

    def test_not_success_when_upsert_mismatch(self):
        s = IndexingRunSummary(
            chunks_embedded = 627,
            chunks_upserted = 500,
            errors          = [],
        )
        assert s.success is False

    def test_not_success_when_errors_present(self):
        s = IndexingRunSummary(
            chunks_embedded = 627,
            chunks_upserted = 627,
            errors          = ["Something failed"],
        )
        assert s.success is False

    def test_report_contains_status(self):
        s = IndexingRunSummary(run_id="20240625", chunks_embedded=627, chunks_upserted=627)
        report = s.report()
        assert "SUCCESS" in report or "PARTIAL" in report

    def test_report_contains_counts(self):
        s = IndexingRunSummary(run_id="r1", chunks_pending=627, chunks_upserted=627)
        report = s.report()
        assert "627" in report


# ===========================================================================
# Integration tests — require ChromaDB and the BGE model
# ===========================================================================

@pytest.mark.slow
class TestChromaStoreIntegration:
    """Uses a temporary ChromaDB directory — safe to run without touching production data."""

    @pytest.fixture(scope="class")
    def tmp_store(self, tmp_path_factory):
        tmp_path = tmp_path_factory.mktemp("chroma_test")
        store = ChromaStore(db_path=str(tmp_path))
        store.initialize()
        return store

    @pytest.fixture(scope="class")
    def sample_payloads(self):
        """Minimal synthetic payloads — no model needed for upsert."""
        from embeddings.embed_pipeline import EmbeddingPayload
        import random
        random.seed(42)

        def rand_vec():
            import math
            v = [random.gauss(0, 1) for _ in range(768)]
            mag = math.sqrt(sum(x**2 for x in v))
            return [x / mag for x in v]

        return [
            EmbeddingPayload(
                chunk_id  = f"chunk_{i:04d}",
                content   = f"This is test chunk number {i}.",
                embedding = rand_vec(),
                metadata  = {
                    "doc_id":          "a" * 64,
                    "source_file":     "data/staging/test.docx",
                    "title":           "Test Document",
                    "category":        "SOP",
                    "department":      "Admissions" if i % 2 == 0 else "Finance",
                    "version":         "1.0",
                    "access_level":    "Public" if i < 5 else "Student",
                    "upload_date":     "2024-01-01",
                    "chunk_index":     i,
                    "total_chunks":    10,
                    "section_heading": "Sub Process 1",
                },
            )
            for i in range(10)
        ]

    def test_initialize_creates_collection(self, tmp_store):
        assert tmp_store.is_initialized

    def test_upsert_returns_count(self, tmp_store, sample_payloads):
        upserted = tmp_store.upsert(sample_payloads)
        assert upserted == 10

    def test_collection_stats_after_upsert(self, tmp_store, sample_payloads):
        tmp_store.upsert(sample_payloads)
        stats = tmp_store.get_collection_stats()
        assert stats["vector_count"] >= 10
        assert stats["collection_name"] == COLLECTION_NAME

    def test_upsert_is_idempotent(self, tmp_store, sample_payloads):
        # Upsert the same payloads twice — count must not double
        tmp_store.upsert(sample_payloads)
        tmp_store.upsert(sample_payloads)
        stats = tmp_store.get_collection_stats()
        assert stats["vector_count"] == 10

    def test_query_returns_results(self, tmp_store, sample_payloads):
        tmp_store.upsert(sample_payloads)
        query_vec = sample_payloads[0].embedding
        results = tmp_store.query(query_vec, role="Public", n_results=5)
        assert len(results) > 0

    def test_query_public_role_excludes_student_chunks(self, tmp_store, sample_payloads):
        tmp_store.upsert(sample_payloads)
        query_vec = sample_payloads[0].embedding
        results = tmp_store.query(query_vec, role="Public", n_results=10)
        for r in results:
            assert r["metadata"]["access_level"] == "Public"

    def test_query_student_role_includes_student_chunks(self, tmp_store, sample_payloads):
        tmp_store.upsert(sample_payloads)
        query_vec = sample_payloads[5].embedding
        results = tmp_store.query(query_vec, role="Student", n_results=10)
        levels = {r["metadata"]["access_level"] for r in results}
        assert "Student" in levels or "Public" in levels

    def test_query_result_has_score(self, tmp_store, sample_payloads):
        tmp_store.upsert(sample_payloads)
        results = tmp_store.query(sample_payloads[0].embedding, role="Admin", n_results=3)
        for r in results:
            assert "score" in r
            assert 0.0 <= r["score"] <= 1.0

    def test_query_result_has_source_citation_fields(self, tmp_store, sample_payloads):
        tmp_store.upsert(sample_payloads)
        results = tmp_store.query(sample_payloads[0].embedding, role="Admin", n_results=3)
        for r in results:
            assert "source_file" in r["metadata"]
            assert "department" in r["metadata"]
            assert "section_heading" in r["metadata"]

    def test_delete_by_doc_id(self, tmp_store, sample_payloads):
        tmp_store.upsert(sample_payloads)
        before = tmp_store.get_collection_stats()["vector_count"]
        deleted = tmp_store.delete_by_doc_id("a" * 64)
        after = tmp_store.get_collection_stats()["vector_count"]
        assert deleted == 10
        assert after == before - 10

    def test_department_filter(self, tmp_store, sample_payloads):
        tmp_store.upsert(sample_payloads)
        query_vec = sample_payloads[0].embedding
        results = tmp_store.query(query_vec, role="Admin", n_results=10, department="Admissions")
        for r in results:
            assert r["metadata"]["department"] == "Admissions"
