import logging
import os
from typing import Optional
from ledger import get_connection

logger = logging.getLogger(__name__)


def _condition_to_sql(field: str, op_dict: dict) -> tuple[str, list]:
    """Converts a single {field: {"$eq"|"$in": value}} condition to SQL."""
    if "$eq" in op_dict:
        return f"{field} = ?", [op_dict["$eq"]]
    if "$in" in op_dict:
        values = list(op_dict["$in"])
        placeholders = ",".join(["?"] * len(values))
        return f"{field} IN ({placeholders})", values
    raise ValueError(f"Unsupported where-clause operator for field '{field}': {op_dict}")


def _where_clause_to_sql(where_clause: Optional[dict]) -> tuple[str, list]:
    """
    Converts a ChromaDB-style metadata where-clause (see retrieval/filters.py)
    into a SQL WHERE fragment (without the "WHERE" keyword) and its params.
    Supports $and, $or, $eq, $in — the operators filters.py actually emits.
    """
    if not where_clause:
        return "", []
    if "$and" in where_clause:
        parts, params = [], []
        for cond in where_clause["$and"]:
            sql, p = _where_clause_to_sql(cond)
            parts.append(f"({sql})")
            params.extend(p)
        return " AND ".join(parts), params
    if "$or" in where_clause:
        parts, params = [], []
        for cond in where_clause["$or"]:
            sql, p = _where_clause_to_sql(cond)
            parts.append(f"({sql})")
            params.extend(p)
        return " OR ".join(parts), params
    field, op_dict = next(iter(where_clause.items()))
    return _condition_to_sql(field, op_dict)


class PGVectorStore:
    """
    A vector store using Supabase/PostgreSQL pgvector extension.
    Implements the same API interface as ChromaStore.
    """
    def __init__(self) -> None:
        self._initialized = False
        self._collection = None

    def initialize(self) -> None:
        if self._initialized:
            return
        
        conn = get_connection()
        cursor = conn.cursor()
        try:
            # 1. Try to enable pgvector extension
            try:
                raw_cursor = cursor._cursor if hasattr(cursor, "_cursor") else cursor
                raw_cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            except Exception as e:
                logger.debug(f"[PGVECTOR] Note: could not run CREATE EXTENSION (it might already be enabled): {e}")

            # 2. Create the embeddings table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS embeddings (
                id VARCHAR(255) PRIMARY KEY,
                doc_id VARCHAR(255) NOT NULL,
                content TEXT NOT NULL,
                embedding vector(768) NOT NULL,
                access_level VARCHAR(50),
                department VARCHAR(255),
                category VARCHAR(255),
                title VARCHAR(255),
                version VARCHAR(50)
            );
            """)
            
            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_doc_id ON embeddings(doc_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_access_level ON embeddings(access_level);")
            
            # HNSW index for cosine distance vector search
            try:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_vector ON embeddings USING hnsw (embedding vector_cosine_ops);")
            except Exception as e:
                logger.warning(f"[PGVECTOR] Could not create HNSW index: {e}. Falling back to standard search.")

            conn.commit()
            self._initialized = True
            logger.info("[PGVECTOR] Supabase pgvector store successfully initialized.")
        except Exception as e:
            conn.rollback()
            logger.error(f"[PGVECTOR] Failed to initialize pgvector store: {e}")
            raise e
        finally:
            conn.close()

    def upsert(self, payloads: list) -> int:
        if not payloads:
            return 0
        
        self.initialize()
        conn = get_connection()
        cursor = conn.cursor()
        total_upserted = 0
        try:
            for p in payloads:
                meta = p.metadata
                emb_str = "[" + ",".join(map(str, p.embedding)) + "]"
                
                cursor.execute("""
                INSERT INTO embeddings (
                    id, doc_id, content, embedding, access_level, department, category, title, version
                ) VALUES (?, ?, ?, ?::vector, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    doc_id = EXCLUDED.doc_id,
                    content = EXCLUDED.content,
                    embedding = EXCLUDED.embedding,
                    access_level = EXCLUDED.access_level,
                    department = EXCLUDED.department,
                    category = EXCLUDED.category,
                    title = EXCLUDED.title,
                    version = EXCLUDED.version
                """, (
                    p.chunk_id,
                    meta.get("doc_id", ""),
                    p.content,
                    emb_str,
                    meta.get("access_level", "Public"),
                    meta.get("department", ""),
                    meta.get("category", ""),
                    meta.get("title", ""),
                    meta.get("version", "1.0")
                ))
                total_upserted += 1
            conn.commit()
            logger.info(f"[PGVECTOR] Successfully upserted {total_upserted} vectors to Supabase.")
            return total_upserted
        except Exception as e:
            conn.rollback()
            logger.error(f"[PGVECTOR] Failed to upsert to pgvector: {e}")
            raise e
        finally:
            conn.close()

    def query(
        self,
        embedding: list[float],
        role: str,
        n_results: int = 10,
        department_filter: Optional[str] = None,
    ) -> list[dict]:
        self.initialize()
        
        from vector_store.chroma_store import ACCESS_HIERARCHY
        allowed_levels = ACCESS_HIERARCHY.get(role, ["Public"])
        
        conn = get_connection()
        cursor = conn.cursor()
        try:
            emb_str = "[" + ",".join(map(str, embedding)) + "]"
            
            sql = """
            SELECT id, content, doc_id, access_level, department, category, title, version,
                   (embedding <=> ?::vector) as distance
            FROM embeddings
            WHERE access_level IN ({})
            """
            
            params = [emb_str]
            placeholders = ",".join(["?"] * len(allowed_levels))
            sql = sql.format(placeholders)
            params.extend(allowed_levels)
            
            if department_filter:
                sql += " AND department = ?"
                params.append(department_filter)
                
            sql += " ORDER BY distance ASC LIMIT ?"
            params.append(n_results)
            
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            
            results = []
            for r in rows:
                dist = float(r.get("distance", 1.0) or 1.0)
                similarity = 1.0 - dist
                results.append({
                    "id": r["id"],
                    "content": r["content"],
                    "score": similarity,
                    "metadata": {
                        "doc_id": r["doc_id"],
                        "access_level": r["access_level"],
                        "department": r["department"],
                        "category": r["category"],
                        "title": r["title"],
                        "version": r["version"]
                    }
                })
            return results
        except Exception as e:
            logger.error(f"[PGVECTOR] Query failed: {e}")
            raise e
        finally:
            conn.close()

    def query_with_filter(
        self,
        query_embedding: list[float],
        where_clause: Optional[dict],
        n_results: int = 10,
    ) -> list[dict]:
        """
        Nearest-neighbour search with a pre-built ChromaDB-style metadata filter
        (see retrieval/filters.py). Mirrors ChromaStore.query_with_filter's
        contract so retrieval/hybrid_search.py's DenseSearchBackend works
        against either vector store backend.
        """
        self.initialize()
        conn = get_connection()
        cursor = conn.cursor()
        try:
            emb_str = "[" + ",".join(map(str, query_embedding)) + "]"

            sql = """
            SELECT id, content, doc_id, access_level, department, category, title, version,
                   (embedding <=> ?::vector) as distance
            FROM embeddings
            """
            params = [emb_str]

            where_sql, where_params = _where_clause_to_sql(where_clause)
            if where_sql:
                sql += f" WHERE {where_sql}"
                params.extend(where_params)

            sql += " ORDER BY distance ASC LIMIT ?"
            params.append(n_results)

            cursor.execute(sql, params)
            rows = cursor.fetchall()

            results = []
            for r in rows:
                dist = float(r.get("distance", 1.0) or 1.0)
                results.append({
                    "chunk_id": r["id"],
                    "content":  r["content"],
                    "distance": dist,
                    "score":    1.0 - dist,
                    "metadata": {
                        "doc_id":       r["doc_id"],
                        "access_level": r["access_level"],
                        "department":   r["department"],
                        "category":     r["category"],
                        "title":        r["title"],
                        "version":      r["version"],
                    },
                })
            return results
        except Exception as e:
            logger.error(f"[PGVECTOR] query_with_filter failed: {e}")
            raise e
        finally:
            conn.close()

    def get_collection_stats(self) -> dict:
        self.initialize()
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT COUNT(*) as cnt FROM embeddings")
            count = cursor.fetchone()["cnt"]
            
            cursor.execute("SELECT COUNT(DISTINCT doc_id) as doc_cnt FROM embeddings")
            doc_count = cursor.fetchone()["doc_cnt"]
            
            return {
                "count": count,
                "vector_count": count,
                "document_count": doc_count,
                "db_path": "Supabase PostgreSQL",
                "backend": "pgvector"
            }
        except Exception as e:
            logger.error(f"[PGVECTOR] Failed to get stats: {e}")
            return {"count": 0, "vector_count": 0, "document_count": 0, "db_path": "Supabase PostgreSQL", "backend": "pgvector"}
        finally:
            conn.close()

    def delete_by_doc_id(self, doc_id: str) -> None:
        self.initialize()
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM embeddings WHERE doc_id = ?", (doc_id,))
            conn.commit()
            logger.info(f"[PGVECTOR] Deleted all embeddings for doc_id: {doc_id}")
        except Exception as e:
            conn.rollback()
            logger.error(f"[PGVECTOR] Failed to delete embeddings for doc_id {doc_id}: {e}")
            raise e
        finally:
            conn.close()

    def collection_exists(self) -> bool:
        self.initialize()
        stats = self.get_collection_stats()
        return stats["count"] > 0
