"""Bootstrap the database with sample data for local development.

Usage:
    python scripts/bootstrap_db.py          # seed fresh data
    python scripts/bootstrap_db.py --reset   # drop + recreate + seed

Requires DATABASE_URL env var (defaults to sqlite:///./backend/assistant.db).
Run from the repository root.
"""

import argparse
import os
import secrets
import sys
from datetime import UTC, datetime, timedelta

# Ensure backend/ is on sys.path so we can import app modules.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models import (
    DigestSubscription,
    FavoriteResult,
    QueryHistory,
    SharedSnippet,
    User,
)
from app.security import hash_password


def drop_tables():
    Base.metadata.drop_all(bind=engine)


def create_tables():
    Base.metadata.create_all(bind=engine)


def seed_data():
    db = SessionLocal()
    try:
        sample_user = User(
            email="alice@example.com",
            password_hash=hash_password("SamplePass123!"),
        )
        db.add(sample_user)
        db.flush()

        sample_analyses = [
            QueryHistory(
                user_id=sample_user.id,
                action="code_review",
                code='def greet(name: str) -> str:\n    return f"Hello, {name}!"',
                result_json='{"score": 85, "issues": [], "suggestions": ["add type hints"]}',
            ),
            QueryHistory(
                user_id=sample_user.id,
                action="debug",
                code="x = [1, 2, 3]\nprint(x[3])",
                result_json='{"error": "IndexError", "fix": "Use x[2] for last element or check list length"}',
            ),
            QueryHistory(
                user_id=sample_user.id,
                action="explain",
                code="from functools import lru_cache\n\n@lru_cache(maxsize=None)\ndef fib(n):\n    return n if n < 2 else fib(n-1) + fib(n-2)",
                result_json='{"explanation": "Memoized Fibonacci using LRU cache"}',
            ),
        ]
        db.add_all(sample_analyses)
        db.flush()

        sample_favorites = [
            FavoriteResult(
                user_id=sample_user.id,
                title="Efficient Fibonacci",
                action="explain",
                code="from functools import lru_cache\n\n@lru_cache(maxsize=None)\ndef fib(n):\n    return n if n < 2 else fib(n-1) + fib(n-2)",
                result_json='{"explanation": "Memoized Fibonacci using LRU cache"}',
            ),
            FavoriteResult(
                user_id=sample_user.id,
                title="List index check",
                action="debug",
                code="if idx < len(items):\n    print(items[idx])",
                result_json='{"fix": "Guard index access with bounds check"}',
            ),
        ]
        db.add_all(sample_favorites)

        sample_digest = DigestSubscription(
            email="alice@example.com",
            is_active=True,
            unsubscribe_token=secrets.token_hex(32),
            subscribed_at=datetime.now(UTC),
            last_sent_at=datetime.now(UTC) - timedelta(days=1),
        )
        db.add(sample_digest)

        sample_snippet = SharedSnippet(
            token=secrets.token_hex(32),
            code="print('Hello, Debugra!')",
            result_json='{"output": "Hello, Debugra!"}',
        )
        db.add(sample_snippet)

        db.commit()
        print(f"  User:          alice@example.com / SamplePass123!")
        print(f"  Queries:       {len(sample_analyses)}")
        print(f"  Favorites:     {len(sample_favorites)}")
        print(f"  Digest sub:    1 (alice@example.com)")
        print(f"  Shared snippet: 1")

    except Exception as exc:
        db.rollback()
        print(f"Error seeding data: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Bootstrap the database with sample data."
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop all tables before seeding (destroys existing data).",
    )
    args = parser.parse_args()

    print(f"Database: {settings.database_url}")

    if args.reset:
        print("Dropping all tables...")
        drop_tables()

    print("Creating tables...")
    create_tables()

    print("Seeding sample data...")
    seed_data()

    print("Done.")


if __name__ == "__main__":
    main()
