"""Unit tests for ledger.py Phase 2/3 APIs."""

import os
import tempfile
import unittest

import ledger


class LedgerPhase23Tests(unittest.TestCase):
    """Tests document and chunk persistence for ingestion pipeline."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._orig_db = ledger.DB_PATH
        ledger.DB_PATH = os.path.join(self._tmpdir.name, "test_ledger.db")
        ledger.initialize_db()

    def tearDown(self):
        ledger.DB_PATH = self._orig_db
        self._tmpdir.cleanup()

    def test_upsert_and_lookup_by_source(self):
        record = {
            "doc_id": "abc123" * 8,
            "source_file": "data/staging/test.docx",
            "original_file": "data/test.doc",
            "title": "Test SOP",
            "category": "SOP",
            "department": "Admissions",
            "version": "1.0",
            "access_level": "Public",
            "upload_date": "2026-01-01",
            "total_chunks": 0,
            "status": "ingested",
            "ingested_at": "2026-01-01T00:00:00",
        }
        ledger.upsert_document(record)

        found = ledger.get_document_by_source("data/staging/test.docx")
        self.assertIsNotNone(found)
        self.assertEqual(found["doc_id"], record["doc_id"])
        self.assertEqual(found["sha256_hash"], record["doc_id"])
        self.assertEqual(found["department"], "Admissions")

    def test_save_chunks_replaces_on_reingest(self):
        doc_id = "deadbeef" * 4
        ledger.upsert_document({
            "doc_id": doc_id,
            "source_file": "data/staging/sop.docx",
            "original_file": "data/sop.doc",
            "title": "SOP",
            "category": "SOP",
            "department": "Academics",
            "version": "1.0",
            "access_level": "Public",
            "upload_date": "2026-01-01",
            "total_chunks": 0,
            "status": "ingested",
            "ingested_at": "2026-01-01T00:00:00",
        })

        chunks_v1 = [
            {
                "chunk_id": "chunk001",
                "doc_id": doc_id,
                "chunk_index": 0,
                "content": "First chunk content.",
                "section_heading": "Name: Test Process",
                "category": "SOP",
                "department": "Academics",
                "access_level": "Public",
                "version": "1.0",
                "source_file": "data/staging/sop.docx",
                "total_chunks": 1,
                "created_at": "2026-01-01T00:00:00",
            }
        ]
        ledger.save_chunks(chunks_v1)
        self.assertEqual(ledger.get_chunk_count(), 1)

        chunks_v2 = [
            {
                "chunk_id": "chunk002",
                "doc_id": doc_id,
                "chunk_index": 0,
                "content": "Updated chunk content.",
                "section_heading": "Name: Test Process",
                "category": "SOP",
                "department": "Academics",
                "access_level": "Public",
                "version": "1.0",
                "source_file": "data/staging/sop.docx",
                "total_chunks": 2,
                "created_at": "2026-01-02T00:00:00",
            },
            {
                "chunk_id": "chunk003",
                "doc_id": doc_id,
                "chunk_index": 1,
                "content": "Second chunk.",
                "section_heading": "Name: Test Process",
                "category": "SOP",
                "department": "Academics",
                "access_level": "Public",
                "version": "1.0",
                "source_file": "data/staging/sop.docx",
                "total_chunks": 2,
                "created_at": "2026-01-02T00:00:00",
            },
        ]
        ledger.save_chunks(chunks_v2)
        self.assertEqual(ledger.get_chunk_count(), 2)
        stored = ledger.get_chunks_by_doc_id(doc_id)
        self.assertEqual(stored[0]["content"], "Updated chunk content.")

    def test_version_supersession(self):
        old_id = "old" * 16
        new_id = "new" * 16

        for doc_id, version in [(old_id, "1.0"), (new_id, "2.0")]:
            ledger.upsert_document({
                "doc_id": doc_id,
                "source_file": f"data/staging/v{version}.docx",
                "original_file": f"data/v{version}.doc",
                "title": "Fees SOP",
                "category": "SOP",
                "department": "Fees And Billing",
                "version": version,
                "access_level": "Public",
                "upload_date": "2026-01-01",
                "total_chunks": 0,
                "status": "ingested",
                "ingested_at": "2026-01-01T00:00:00",
            })

        ledger.mark_document_superseded(old_id)
        active = ledger.get_document_by_department("Fees And Billing")
        self.assertEqual(active["doc_id"], new_id)

        old = ledger.get_document_by_doc_id(old_id)
        self.assertEqual(old["status"], "superseded")

    def test_phase1_register_still_works(self):
        ledger.register_document(
            filepath="data/legacy.doc",
            sha256_hash="hash123",
            status="assessed",
            metadata={"title": "Legacy", "department": "General"},
        )
        doc = ledger.get_document("data/legacy.doc")
        self.assertEqual(doc["status"], "assessed")
        self.assertEqual(doc["title"], "Legacy")


if __name__ == "__main__":
    unittest.main()
