"""Create a demo user account for QyverixAI."""

from __future__ import annotations

import os
import sys

from sqlalchemy import select

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.database import Base, SessionLocal, engine
from app.models import User
from app.security import hash_password

DEMO_EMAIL = "demo@qyverixai.com"


def main() -> None:
    password = os.getenv("DEMO_PASSWORD")
    if not password:
        print("Error: DEMO_PASSWORD environment variable is required.", file=sys.stderr)
        sys.exit(1)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        existing = db.execute(select(User).where(User.email == DEMO_EMAIL)).scalar_one_or_none()
        if existing is not None:
            existing.password_hash = hash_password(password)
            existing.is_demo = True
            db.commit()
            print("Updated existing demo user.")
        else:
            user = User(
                email=DEMO_EMAIL,
                password_hash=hash_password(password),
                is_demo=True,
            )
            db.add(user)
            db.commit()
            print("Created demo user.")
    finally:
        db.close()

    print()
    print("Demo credentials:")
    print(f"  Email:    {DEMO_EMAIL}")
    print(f"  Password: {password}")
    print()
    print("Send X-Demo-User: true on analysis requests to apply the demo rate limit.")


if __name__ == "__main__":
    main()
