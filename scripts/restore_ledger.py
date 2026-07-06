#!/usr/bin/env python3
"""
scripts/restore_ledger.py
-------------------------
Phase 2: Ingestion Ledger Recovery

Connects to the persistent ChromaDB store, fetches all chunks,
extracts document and chunk metadata, and inserts them into the SQLite database.
Never recreates or generates dummy source files.
"""

import os
import sys
from collections import defaultdict
from datetime import datetime

# Add project root to sys.path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import ledger
from vector_store.chroma_store import get_chroma_store, COLLECTION_NAME


def main():
    print("=" * 60)
    print("STARTING LEDGER RECOVERY FROM CHROMADB METADATA")
    print("=" * 60)

    # 1. Initialize SQLite Database
    print("Initializing SQLite Ledger database...")
    ledger.initialize_db()

    # 2. Connect to ChromaDB
    print("Connecting to ChromaDB store...")
    try:
        store = get_chroma_store()
        collection = store._collection
        if collection is None:
            print("ERROR: Failed to fetch ChromaDB collection.")
            sys.exit(1)
    except Exception as exc:
        print(f"ERROR: Could not connect to ChromaDB: {exc}")
        sys.exit(1)

    count = collection.count()
    print(f"Found {count} vectors in ChromaDB collection '{COLLECTION_NAME}'")

    if count == 0:
        print("WARNING: ChromaDB is empty. Nothing to restore.")
        return

    # 3. Retrieve all items from ChromaDB
    print("Fetching all items from ChromaDB (metadatas & documents)...")
    try:
        # Fetching in one large batch since it is only 627 records
        results = collection.get(include=["metadatas", "documents"])
    except Exception as exc:
        print(f"ERROR: Failed to retrieve data from ChromaDB: {exc}")
        sys.exit(1)

    ids = results.get("ids") or []
    metadatas = results.get("metadatas") or []
    documents = results.get("documents") or []

    print(f"Retrieved {len(ids)} items.")

    # Group chunks by doc_id to reconstruct documents
    doc_chunks = defaultdict(list)

    for i in range(len(ids)):
        chunk_id = ids[i]
        meta = metadatas[i]
        content = documents[i]

        doc_id = meta.get("doc_id")
        if not doc_id:
            print(f"WARNING: Chunk {chunk_id} has no doc_id. Skipping.")
            continue

        doc_chunks[doc_id].append({
            "chunk_id": chunk_id,
            "content": content,
            "metadata": meta
        })

    print(f"Grouped into {len(doc_chunks)} unique documents.")

    # 4. Save documents and chunks to SQLite ledger
    now = datetime.utcnow().isoformat()
    docs_restored = 0
    chunks_restored = 0

    for doc_id, chunks in doc_chunks.items():
        # Sort chunks by chunk_index to ensure correct order
        chunks.sort(key=lambda x: int(x["metadata"].get("chunk_index", 0)))

        # Extract representative metadata from the first chunk
        first_chunk = chunks[0]
        meta = first_chunk["metadata"]

        source_file = meta.get("source_file", "")
        title = meta.get("title", "")
        category = meta.get("category", "SOP")
        department = meta.get("department", "General")
        version = meta.get("version", "1.0")
        access_level = meta.get("access_level", "Public")
        upload_date = meta.get("upload_date", "")

        # Format DocumentRecord dict
        doc_record = {
            "doc_id": doc_id,
            "source_file": source_file,
            "original_file": source_file.replace("staging/", "").replace(".docx", ".doc"), # rough proxy
            "title": title,
            "category": category,
            "department": department,
            "version": version,
            "access_level": access_level,
            "upload_date": upload_date,
            "total_chunks": len(chunks),
            "status": "embedded",
            "ingested_at": now
        }

        # Upsert document into ledger
        try:
            ledger.upsert_document(doc_record)
            docs_restored += 1
        except Exception as exc:
            print(f"ERROR: Failed to save document {doc_id} to ledger: {exc}")
            continue

        # Format ChunkRecords
        chunk_records = []
        for idx, chunk in enumerate(chunks):
            cm = chunk["metadata"]
            chunk_records.append({
                "chunk_id": chunk["chunk_id"],
                "doc_id": doc_id,
                "chunk_index": int(cm.get("chunk_index", idx)),
                "content": chunk["content"],
                "section_heading": cm.get("section_heading", ""),
                "category": cm.get("category", category),
                "department": cm.get("department", department),
                "access_level": cm.get("access_level", access_level),
                "version": cm.get("version", version),
                "source_file": cm.get("source_file", source_file),
                "total_chunks": len(chunks),
                "created_at": now
            })

        # Save chunks into ledger
        try:
            ledger.save_chunks(chunk_records)
            # Stamp embedded_at to mark them as completed Phase 4
            ledger.mark_chunks_embedded([cr["chunk_id"] for cr in chunk_records])
            chunks_restored += len(chunk_records)
        except Exception as exc:
            print(f"ERROR: Failed to save chunks for document {doc_id} to ledger: {exc}")

    print("-" * 60)
    print("RECOVERY COMPLETE")
    print(f"Documents restored: {docs_restored}")
    print(f"Chunks restored:    {chunks_restored}")
    print("=" * 60)


if __name__ == "__main__":
    main()
