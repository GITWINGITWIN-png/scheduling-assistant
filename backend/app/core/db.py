"""The shared store: one SQLite file, opened through SQLAlchemy.

Why these choices (from the agreed plan, q_db):
- SQLite is a single file in ~/.secretary: no server to install, and a backup is
  a file copy (step 10).
- WAL mode lets the web page read while the clock or the Discord bot is writing.
  Without it, a reader can hit "database is locked" during a write.
- Sessions are the plain (synchronous) kind. The app is async (FastAPI,
  discord.py), but every query here takes well under a millisecond, so calling
  them directly from async code is simpler than an async driver and costs
  nothing you would notice.
- Table changes go through Alembic migrations (backend/migrations/), never
  create_all(). Each change is then a reviewable file that can also be undone.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

from sqlalchemy import DateTime, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.types import TypeDecorator

from app.core.config import BACKEND_DIR, get_config


def now() -> datetime:
    """The current time, always timezone-aware UTC. Use this, not datetime.now()."""
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator):
    """A datetime column that always comes back timezone-aware (UTC).

    SQLite has no time-zone type: it stores text and returns naive datetimes. A
    naive datetime compared with an aware one raises TypeError, and a naive one
    shown to you is ambiguous. So: convert to UTC on the way in, and put the UTC
    label back on the way out. Convert to your local zone only when displaying.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime given to a UTCDateTime column; use core.db.now()")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect):
        return value.replace(tzinfo=UTC) if value is not None else None


class Base(DeclarativeBase):
    """Parent of every table class. Alembic compares Base.metadata with the database."""


def _make_engine() -> Engine:
    engine = create_engine(
        f"sqlite:///{get_config().db_path}",
        # The bot, the clock and web requests use the engine from different threads.
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")  # SQLite ignores foreign keys unless asked
        cur.execute("PRAGMA busy_timeout=5000")  # wait up to 5 s for a writer instead of failing
        cur.close()

    return engine


engine = _make_engine()
SessionLocal = sessionmaker(engine, expire_on_commit=False)


@contextmanager
def session() -> Iterator[Session]:
    """`with session() as s: ...` commits on success and rolls back on any error."""
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except BaseException:
        s.rollback()
        raise
    finally:
        s.close()


def migrate() -> None:
    """Bring the database up to the newest migration (runs at startup).

    After you pull new code and restart, new tables or columns are created
    automatically. Running it on an up-to-date database does nothing.
    """
    from alembic import command
    from alembic.config import Config as AlembicConfig

    cfg = AlembicConfig(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    command.upgrade(cfg, "head")
