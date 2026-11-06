"""Alembic's entry point: how migrations reach v2's database.

Run from backend/:
    uv run alembic upgrade head                                # apply every new migration
    uv run alembic revision --autogenerate -m "add people"     # draft one from the table classes
    uv run alembic downgrade -1                                # undo the latest one

The app also runs `upgrade head` by itself at startup (core/db.migrate).
"""

from alembic import context

import app.core.tables  # noqa: F401  registers the shared tables on Base.metadata
from app.core.db import Base, engine

# Each later phase that adds tables imports its module here too:
import app.features.mail.tables  # noqa: F401,E402  B2: people, emails, followups
import app.features.classroom.tables  # noqa: F401,E402  B3: courses, course_items
import app.features.briefs.tables  # noqa: F401,E402  B4: briefs
import app.features.projects.tables  # noqa: F401,E402  B5: projects, project news

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """`alembic upgrade head --sql` prints the SQL instead of running it."""
    context.configure(url=str(engine.url), target_metadata=target_metadata, literal_binds=True, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with engine.connect() as connection:
        # A batch migration rebuilds a table: new table, copy the rows, drop the old one,
        # rename. With foreign keys on, SQLite refuses to drop `tasks` while `blocks` point
        # at it (found undoing a B3 migration on a copy of the real database), so they are off
        # while migrating and every reference is checked once at the end instead. SQLite only
        # accepts this switch outside a transaction, hence the commit right after it.
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.commit()
        try:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                # SQLite can't ALTER most column changes. In batch mode Alembic builds the new
                # table, copies the rows across and swaps it in, so later migrations just work.
                render_as_batch=True,
            )
            with context.begin_transaction():
                context.run_migrations()
            broken = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
            if broken:
                raise RuntimeError(f"the migration left rows pointing at nothing: {broken[:5]}")
        finally:
            connection.rollback()  # end any transaction left open, so the switch below takes effect
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")  # the app's connections rely on it
            connection.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
