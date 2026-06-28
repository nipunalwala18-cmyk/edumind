"""
Seed script — wipes and recreates the SQLite database with four test accounts.
Run from the project root: python seed_users.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))

from backend.database import Base, SessionLocal, User, engine
from backend.auth import hash_password

SEED_USERS = [
    {"username": "public_user",  "password": "Public@123",  "role": "Public"},
    {"username": "student_test", "password": "Student@123", "role": "Student"},
    {"username": "faculty_test", "password": "Faculty@123", "role": "Faculty"},
    {"username": "admin_test",   "password": "Admin@123",   "role": "Admin"},
]


def seed():
    print("Dropping existing tables...")
    Base.metadata.drop_all(bind=engine)
    print("Creating fresh schema...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        for entry in SEED_USERS:
            db.add(User(
                username=entry["username"],
                hashed_password=hash_password(entry["password"]),
                role=entry["role"],
            ))
        db.commit()
        print("\nSeeded accounts:")
        for e in SEED_USERS:
            print(f"  {e['role']:10s}  {e['username']:20s}  {e['password']}")
        print("\nDatabase ready: ./institutional.db")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
