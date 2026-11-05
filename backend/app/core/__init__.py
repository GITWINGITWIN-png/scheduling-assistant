"""Core: the shared kernel every other layer uses.

Planned contents, added step by step in B1 (names may still change):

- config     settings read from backend/.env                         (step 3)
- db         the SQLite store: SQLAlchemy tables, Alembic migrations   (step 3)
- llm        the one way to call Claude: Sonnet or Opus + effort,
             with tokens recorded on every call                       (step 4)
- clock      the secretary's clock: scheduled rounds, and catching up
             on the rounds missed while the machine was off           (step 5)
- actions    the action log: everything the secretary does is written
             here, with an undo where the action can be undone        (step 8)

Rule: core imports nothing from connectors/, features/ or api/.
Everything else may import core.
"""
