"""
chunk_validation.py
-------------------
Read-only validation of chunked documents stored in ingestion_ledger.db.

Loads all rows from the SQLite `chunks` table, computes quality metrics,
runs integrity checks, samples random chunks for manual review, and writes
chunk_validation_report.md.

Does not modify the database or any source data.
"""

from __future__ import annotations

import os
import random
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from statistics import mean
from typing import Any

try:
    import ledger
except ImportError:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    import ledger

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
REPORT_PATH = os.path.join(PROJECT_ROOT, "chunk_validation_report.md")
OVER_SIZE_THRESHOLD = 1500
SAMPLE_SIZE = 10

# Metadata columns persisted in the chunks table (excluding content / ids / timestamps).
REQUIRED_METADATA_FIELDS = (
    "doc_id",
    "source_file",
    "category",
    "department",
    "version",
    "access_level",
    "chunk_index",
    "total_chunks",
)

VALID_ACCESS_LEVELS = {"Public", "Student", "Faculty", "Admin"}


@dataclass
class ValidationResult:
    """Aggregated read-only validation output."""

    generated_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    total_chunks: int = 0
    avg_chunk_size: float = 0.0
    largest_chunk: dict[str, Any] | None = None
    smallest_chunk: dict[str, Any] | None = None
    empty_chunks: list[dict[str, Any]] = field(default_factory=list)
    over_size_chunks: list[dict[str, Any]] = field(default_factory=list)
    missing_metadata_chunks: list[dict[str, Any]] = field(default_factory=list)
    duplicate_chunk_ids: list[str] = field(default_factory=list)
    doc_id_issues: list[str] = field(default_factory=list)
    access_level_issues: list[str] = field(default_factory=list)
    sample_chunks: list[dict[str, Any]] = field(default_factory=list)
    chunks_by_department: Counter = field(default_factory=Counter)
    chunks_by_access_level: Counter = field(default_factory=Counter)

    @property
    def passed(self) -> bool:
        return not any([
            self.empty_chunks,
            self.duplicate_chunk_ids,
            self.doc_id_issues,
            self.access_level_issues,
        ])


def _load_all_chunks() -> list[dict[str, Any]]:
    """Loads every chunk row from SQLite (read-only)."""
    conn = ledger.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM chunks ORDER BY doc_id, chunk_index")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def _load_document_doc_ids() -> set[str]:
    """Returns doc_id values registered in the documents table."""
    conn = ledger.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT doc_id FROM documents WHERE doc_id IS NOT NULL")
    doc_ids = {row["doc_id"] for row in cursor.fetchall()}
    conn.close()
    return doc_ids


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, int) and value < 0:
        return True
    return False


def _chunk_summary(chunk: dict[str, Any]) -> dict[str, Any]:
    """Returns a compact dict describing a chunk for reports."""
    content = chunk.get("content") or ""
    return {
        "chunk_id": chunk.get("chunk_id", ""),
        "doc_id": chunk.get("doc_id", ""),
        "chunk_index": chunk.get("chunk_index"),
        "source_file": chunk.get("source_file", ""),
        "department": chunk.get("department", ""),
        "access_level": chunk.get("access_level", ""),
        "char_count": len(content),
        "content_preview": content[:300].replace("\n", " ").strip(),
    }


def _find_missing_metadata(chunk: dict[str, Any]) -> list[str]:
    missing = []
    for field_name in REQUIRED_METADATA_FIELDS:
        if _is_missing(chunk.get(field_name)):
            missing.append(field_name)
    return missing


def validate_chunks(
    chunks: list[dict[str, Any]],
    known_doc_ids: set[str],
    sample_size: int = SAMPLE_SIZE,
) -> ValidationResult:
    """Runs all read-only validation checks against loaded chunk rows."""
    result = ValidationResult()
    result.total_chunks = len(chunks)

    if not chunks:
        return result

    sizes = [(len(c.get("content") or ""), c) for c in chunks]
    result.avg_chunk_size = round(mean(size for size, _ in sizes), 1)

    _, largest = max(sizes, key=lambda item: item[0])
    _, smallest = min(sizes, key=lambda item: item[0])
    result.largest_chunk = _chunk_summary(largest)
    result.smallest_chunk = _chunk_summary(smallest)

    for chunk in chunks:
        content = chunk.get("content") or ""
        char_count = len(content)

        if not content.strip():
            result.empty_chunks.append(_chunk_summary(chunk))

        if char_count > OVER_SIZE_THRESHOLD:
            result.over_size_chunks.append(_chunk_summary(chunk))

        missing_fields = _find_missing_metadata(chunk)
        if missing_fields:
            summary = _chunk_summary(chunk)
            summary["missing_fields"] = missing_fields
            result.missing_metadata_chunks.append(summary)

        dept = chunk.get("department") or "Unknown"
        result.chunks_by_department[dept] += 1

        level = chunk.get("access_level") or ""
        result.chunks_by_access_level[level or "(missing)"] += 1

    # chunk_id uniqueness
    id_counts = Counter(c.get("chunk_id") for c in chunks)
    result.duplicate_chunk_ids = [
        cid for cid, count in id_counts.items() if cid and count > 1
    ]

    # document_id consistency
    by_doc: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for chunk in chunks:
        by_doc[chunk.get("doc_id", "")].append(chunk)

    for doc_id, doc_chunks in by_doc.items():
        if not doc_id:
            result.doc_id_issues.append("Found chunk(s) with empty doc_id.")
            continue

        if doc_id not in known_doc_ids:
            result.doc_id_issues.append(
                f"doc_id '{doc_id[:16]}...' not found in documents table "
                f"({len(doc_chunks)} chunk(s))."
            )

        source_files = {c.get("source_file") for c in doc_chunks}
        departments = {c.get("department") for c in doc_chunks}
        categories = {c.get("category") for c in doc_chunks}
        versions = {c.get("version") for c in doc_chunks}
        access_levels = {c.get("access_level") for c in doc_chunks}

        if len(source_files) > 1:
            result.doc_id_issues.append(
                f"doc_id '{doc_id[:16]}...' has inconsistent source_file values: "
                f"{sorted(f for f in source_files if f)}."
            )
        if len(departments) > 1:
            result.doc_id_issues.append(
                f"doc_id '{doc_id[:16]}...' has inconsistent department values."
            )
        if len(categories) > 1:
            result.doc_id_issues.append(
                f"doc_id '{doc_id[:16]}...' has inconsistent category values."
            )
        if len(versions) > 1:
            result.doc_id_issues.append(
                f"doc_id '{doc_id[:16]}...' has inconsistent version values."
            )
        if len(access_levels) > 1:
            result.doc_id_issues.append(
                f"doc_id '{doc_id[:16]}...' has inconsistent access_level values."
            )

        declared_totals = {c.get("total_chunks") for c in doc_chunks}
        actual_count = len(doc_chunks)
        if declared_totals != {actual_count}:
            result.doc_id_issues.append(
                f"doc_id '{doc_id[:16]}...' total_chunks mismatch: "
                f"declared={sorted(declared_totals)}, actual={actual_count}."
            )

        indices = sorted(c.get("chunk_index") for c in doc_chunks)
        expected = list(range(actual_count))
        if indices != expected:
            result.doc_id_issues.append(
                f"doc_id '{doc_id[:16]}...' chunk_index sequence invalid: "
                f"expected 0..{actual_count - 1}, got gaps or duplicates."
            )

    # access_level presence and validity
    for chunk in chunks:
        level = chunk.get("access_level")
        chunk_id = chunk.get("chunk_id", "?")
        if _is_missing(level):
            result.access_level_issues.append(
                f"chunk_id '{chunk_id}': access_level is missing."
            )
        elif level not in VALID_ACCESS_LEVELS:
            result.access_level_issues.append(
                f"chunk_id '{chunk_id}': access_level '{level}' is not a recognized value."
            )

    sample_count = min(sample_size, len(chunks))
    result.sample_chunks = [
        _chunk_summary(c) for c in random.sample(chunks, sample_count)
    ]
    for sample in result.sample_chunks:
        full = next(c for c in chunks if c["chunk_id"] == sample["chunk_id"])
        sample["content"] = full.get("content", "")

    return result


def _format_chunk_block(chunk: dict[str, Any], index: int) -> list[str]:
    lines = [
        f"### Sample {index}: `{chunk['chunk_id']}`",
        "",
        f"- **Document:** `{chunk['doc_id'][:16]}...`",
        f"- **Source:** `{chunk['source_file']}`",
        f"- **Department:** {chunk['department']}",
        f"- **Access Level:** {chunk['access_level']}",
        f"- **Chunk Index:** {chunk['chunk_index']}",
        f"- **Size:** {chunk['char_count']} characters",
        "",
        "```",
        chunk.get("content", chunk.get("content_preview", "")),
        "```",
        "",
    ]
    return lines


def generate_report(result: ValidationResult) -> str:
    """Builds the markdown validation report."""
    status = "PASSED" if result.passed else "ISSUES DETECTED"
    lines = [
        "# Chunk Validation Report",
        "",
        f"**Report Generated On:** {result.generated_at}",
        "",
        f"**Overall Status:** {status}",
        "",
        "---",
        "",
        "## 1. Summary Statistics",
        "",
        f"* **Total Chunks:** {result.total_chunks}",
        f"* **Average Chunk Size:** {result.avg_chunk_size} characters",
        "",
    ]

    if result.largest_chunk:
        lc = result.largest_chunk
        lines += [
            f"* **Largest Chunk:** `{lc['chunk_id']}` — {lc['char_count']} chars "
            f"({lc['department']}, index {lc['chunk_index']})",
        ]
    if result.smallest_chunk:
        sc = result.smallest_chunk
        lines += [
            f"* **Smallest Chunk:** `{sc['chunk_id']}` — {sc['char_count']} chars "
            f"({sc['department']}, index {sc['chunk_index']})",
        ]

    lines += [
        "",
        "### Chunks by Department",
        "",
        "| Department | Count |",
        "| --- | --- |",
    ]
    for dept, count in result.chunks_by_department.most_common():
        lines.append(f"| {dept} | {count} |")

    lines += [
        "",
        "### Chunks by Access Level",
        "",
        "| Access Level | Count |",
        "| --- | --- |",
    ]
    for level, count in result.chunks_by_access_level.most_common():
        lines.append(f"| {level} | {count} |")

    lines += [
        "",
        "---",
        "",
        "## 2. Quality Flags",
        "",
        f"### Empty Chunks ({len(result.empty_chunks)})",
        "",
    ]
    if result.empty_chunks:
        lines.append("| chunk_id | doc_id | chunk_index | source_file |")
        lines.append("| --- | --- | --- | --- |")
        for c in result.empty_chunks:
            lines.append(
                f"| `{c['chunk_id']}` | `{c['doc_id'][:16]}...` | "
                f"{c['chunk_index']} | `{c['source_file']}` |"
            )
    else:
        lines.append("*No empty chunks detected.*")

    lines += [
        "",
        f"### Chunks Over {OVER_SIZE_THRESHOLD} Characters ({len(result.over_size_chunks)})",
        "",
    ]
    if result.over_size_chunks:
        lines.append("| chunk_id | chars | department | chunk_index | preview |")
        lines.append("| --- | --- | --- | --- | --- |")
        for c in sorted(result.over_size_chunks, key=lambda x: -x["char_count"]):
            preview = c["content_preview"][:80].replace("|", "\\|")
            lines.append(
                f"| `{c['chunk_id']}` | {c['char_count']} | {c['department']} | "
                f"{c['chunk_index']} | {preview}... |"
            )
    else:
        lines.append(f"*No chunks exceed {OVER_SIZE_THRESHOLD} characters.*")

    lines += [
        "",
        f"### Chunks With Missing Metadata ({len(result.missing_metadata_chunks)})",
        "",
    ]
    if result.missing_metadata_chunks:
        lines.append("| chunk_id | missing_fields | source_file |")
        lines.append("| --- | --- | --- |")
        for c in result.missing_metadata_chunks:
            fields = ", ".join(c["missing_fields"])
            lines.append(
                f"| `{c['chunk_id']}` | {fields} | `{c['source_file']}` |"
            )
    else:
        lines.append("*All chunks have required metadata fields populated.*")

    lines += [
        "",
        "---",
        "",
        "## 3. Integrity Checks",
        "",
        "### chunk_id Uniqueness",
        "",
    ]
    if result.duplicate_chunk_ids:
        lines.append(f"**FAILED** — {len(result.duplicate_chunk_ids)} duplicate chunk_id(s):")
        for cid in result.duplicate_chunk_ids:
            lines.append(f"* `{cid}`")
    else:
        lines.append(f"**PASSED** — All {result.total_chunks} chunk_id values are unique.")

    lines += [
        "",
        "### document_id Consistency",
        "",
    ]
    if result.doc_id_issues:
        lines.append(f"**FAILED** — {len(result.doc_id_issues)} issue(s):")
        for issue in result.doc_id_issues:
            lines.append(f"* {issue}")
    else:
        lines.append(
            "**PASSED** — All doc_id values reference registered documents with "
            "consistent metadata and valid chunk_index sequences."
        )

    lines += [
        "",
        "### access_level Presence",
        "",
    ]
    if result.access_level_issues:
        lines.append(f"**FAILED** — {len(result.access_level_issues)} issue(s):")
        for issue in result.access_level_issues:
            lines.append(f"* {issue}")
    else:
        lines.append(
            "**PASSED** — Every chunk has a valid access_level "
            f"({', '.join(sorted(VALID_ACCESS_LEVELS))})."
        )

    lines += [
        "",
        "---",
        "",
        f"## 4. Random Sample ({len(result.sample_chunks)} Chunks)",
        "",
    ]
    for i, chunk in enumerate(result.sample_chunks, start=1):
        lines.extend(_format_chunk_block(chunk, i))

    lines.append("---")
    lines.append("")
    lines.append("*Read-only validation — no data was modified.*")
    lines.append("")

    return "\n".join(lines)


def print_console_summary(result: ValidationResult) -> None:
    """Prints key metrics and random samples to stdout."""
    print("=" * 60)
    print("CHUNK VALIDATION (read-only)")
    print("=" * 60)
    print(f"  Total chunks          : {result.total_chunks}")
    print(f"  Average chunk size    : {result.avg_chunk_size} chars")
    if result.largest_chunk:
        print(
            f"  Largest chunk         : {result.largest_chunk['char_count']} chars "
            f"({result.largest_chunk['chunk_id']})"
        )
    if result.smallest_chunk:
        print(
            f"  Smallest chunk        : {result.smallest_chunk['char_count']} chars "
            f"({result.smallest_chunk['chunk_id']})"
        )
    print(f"  Empty chunks          : {len(result.empty_chunks)}")
    print(f"  Over {OVER_SIZE_THRESHOLD} chars        : {len(result.over_size_chunks)}")
    print(f"  Missing metadata      : {len(result.missing_metadata_chunks)}")
    print(f"  Duplicate chunk_ids   : {len(result.duplicate_chunk_ids)}")
    print(f"  doc_id issues         : {len(result.doc_id_issues)}")
    print(f"  access_level issues   : {len(result.access_level_issues)}")
    print(f"  Overall status        : {'PASSED' if result.passed else 'ISSUES DETECTED'}")
    print("-" * 60)
    print(f"  Random sample ({len(result.sample_chunks)} chunks):")
    print("-" * 60)
    for i, chunk in enumerate(result.sample_chunks, start=1):
        print(f"\n--- Sample {i}: {chunk['chunk_id']} ({chunk['char_count']} chars) ---")
        print(f"  Department   : {chunk['department']}")
        print(f"  Access Level : {chunk['access_level']}")
        print(f"  Source       : {chunk['source_file']}")
        print(f"  Content:")
        print(chunk.get("content", chunk.get("content_preview", "")))
    print("=" * 60)
    print(f"Report written to: {REPORT_PATH}")
    print("=" * 60)


def run_validation(sample_size: int = SAMPLE_SIZE) -> ValidationResult:
    """Loads chunks, validates, prints summary, and writes the markdown report."""
    ledger.initialize_db()
    chunks = _load_all_chunks()
    known_doc_ids = _load_document_doc_ids()
    result = validate_chunks(chunks, known_doc_ids, sample_size=sample_size)

    report = generate_report(result)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)

    print_console_summary(result)
    return result


if __name__ == "__main__":
    run_validation()
