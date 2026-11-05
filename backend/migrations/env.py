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

# Each later phase that adds tables imports its module here too, for example:
# import app.features.people.tables

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """`alembic upgrade head --sql` prints the SQL instead of running it."""
    context.configure(url=str(engine.url), target_metadata=target_metadata, literal_binds=True, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # SQLite can't ALTER most column changes. In batch mode Alembic builds the new
            # table, copies the rows across and swaps it in, so later migrations just work.
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
