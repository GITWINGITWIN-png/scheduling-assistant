"""Database setup (SQLAlchemy 2.0 style).

Google Calendar holds the *events*. This local SQLite database holds the
"smart layer" the secretary reasons over: your projects, their progress, and
the plans it generates. Keeping them separate means Google stays the source of
truth for the calendar while we own the planning brain.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

# `check_same_thread=False` is the standard SQLite tweak so the connection can
# be used across FastAPI's threadpool. Harmless for single-user local dev.
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Base class all ORM models inherit from."""


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a DB session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables for any imported models. Called on startup."""
    # Import models so they register on Base.metadata before create_all.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
