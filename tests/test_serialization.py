"""Unit tests for table-aware SOP serialization and chunking."""

import unittest
from unittest.mock import MagicMock

from chunk_schema import AccessLevel, DocumentCategory, DocumentRecord, DocumentStatus
from chunker import chunk_document, _split_into_atomic_blocks
from ingestion_pipeline import (
    _extract_sub_process_name,
    _serialize_sop_table,
    clean_text,
)


class MockCell:
    def __init__(self, text):
        self.text = text


class MockRow:
    def __init__(self, texts):
        self.cells = [MockCell(t) for t in texts]


class MockTable:
    def __init__(self, rows):
        self.rows = [MockRow(r) for r in rows]


SAMPLE_SOP_TABLE = MockTable([
    ["1.1 Sub Process: Conducting Term Test", "1.1 Sub Process: Conducting Term Test"],
    ["Key Objectives", "Ensure fair evaluation of student performance."],
    ["Key Inputs", "Question paper | Answer sheets | Invigilator list"],
    ["Process Description", "The term test shall be conducted as per academic calendar."],
    ["Key Performers", "Faculty | Examination cell"],
    ["Key Outputs", "Evaluated answer sheets | Marks entry"],
])


class SerializationTests(unittest.TestCase):
    def test_sub_process_name_extraction(self):
        name = _extract_sub_process_name("1.1 Sub Process: Conducting Term Test")
        self.assertEqual(name, "Conducting Term Test")

    def test_sop_table_serialization_format(self):
        result = _serialize_sop_table(SAMPLE_SOP_TABLE)
        self.assertIn("[SUB PROCESS]", result)
        self.assertIn("Name: Conducting Term Test", result)
        self.assertIn("Objectives:", result)
        self.assertIn("Inputs:", result)
        self.assertIn("Process Description:", result)
        self.assertIn("Performers:", result)
        self.assertIn("Outputs:", result)
        self.assertIn("Ensure fair evaluation", result)

    def test_clean_text_normalizes_unicode(self):
        raw = "Process\u2013step\u00a0with\u2019quotes"
        cleaned = clean_text(raw)
        self.assertNotIn("\u2013", cleaned)
        self.assertNotIn("\u00a0", cleaned)


class ChunkingTests(unittest.TestCase):
    SAMPLE_TEXT = (
        "[PROCESS: Admissions]\n\n"
        "[SUB PROCESS]\n"
        "Name: Conducting Term Test\n"
        "Objectives:\n"
        "Ensure fair evaluation.\n\n"
        "[SUB PROCESS]\n"
        "Name: Document Verification\n"
        "Objectives:\n"
        "Verify all submitted documents.\n"
    )

    def test_atomic_blocks_split_at_sub_process(self):
        blocks = _split_into_atomic_blocks(self.SAMPLE_TEXT)
        self.assertGreaterEqual(len(blocks), 2)
        self.assertTrue(any("Conducting Term Test" in b[0] for b in blocks))
        self.assertTrue(any("Document Verification" in b[0] for b in blocks))

    def test_chunk_document_preserves_sub_process(self):
        doc = DocumentRecord(
            doc_id="test" * 16,
            source_file="data/staging/test.docx",
            title="Test SOP",
            category=DocumentCategory.SOP,
            department="Examination",
            version="1.0",
            access_level=AccessLevel.PUBLIC,
            status=DocumentStatus.INGESTED,
        )
        chunks = chunk_document(doc, self.SAMPLE_TEXT)
        self.assertGreaterEqual(len(chunks), 2)
        self.assertTrue(all(c.metadata.total_chunks == len(chunks) for c in chunks))
        self.assertTrue(all(c.metadata.access_level == "Public" for c in chunks))
        headings = [c.metadata.section_heading for c in chunks]
        self.assertTrue(any("Conducting Term Test" in h for h in headings))


if __name__ == "__main__":
    unittest.main()
