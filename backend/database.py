from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///./institutional.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False)  # 'Public','Student','Faculty','Admin'
    is_committee_head = Column(Boolean, nullable=False, default=False)
    committee_name = Column(String, nullable=True)


class CommitteeUpload(Base):
    __tablename__ = "committee_uploads"
    id = Column(Integer, primary_key=True, index=True)
    uploaded_by = Column(String, nullable=False, index=True)
    committee_name = Column(String, nullable=True)
    original_filename = Column(String, nullable=False)
    stored_path = Column(String, nullable=False)
    sha256_hash = Column(String, nullable=False, index=True)
    title = Column(String, nullable=True)
    department = Column(String, nullable=True)
    approval_status = Column(String, nullable=False, default="pending")  # 'pending'|'approved'|'rejected'
    rejection_reason = Column(Text, nullable=True)
    reviewed_by = Column(String, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    doc_id = Column(String, nullable=True)
    submitted_at = Column(DateTime, default=datetime.utcnow)


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, nullable=False, index=True)
    session_id = Column(String, nullable=False, index=True)
    content = Column(Text, nullable=False)
    is_user = Column(Boolean, nullable=False)
    sources = Column(Text, nullable=True)   # JSON list stored as string
    timestamp = Column(DateTime, default=datetime.utcnow)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_column(cursor, table: str, column: str, definition: str) -> None:
    """Adds a column to an existing table if it is not already present."""
    cursor.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cursor.fetchall()}
    if column not in existing:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def migrate_user_columns():
    """Extends a pre-existing users table with committee-head columns."""
    conn = engine.raw_connection()
    try:
        cursor = conn.cursor()
        _ensure_column(cursor, "users", "is_committee_head", "BOOLEAN NOT NULL DEFAULT 0")
        _ensure_column(cursor, "users", "committee_name", "TEXT")
        conn.commit()
    finally:
        conn.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    migrate_user_columns()
