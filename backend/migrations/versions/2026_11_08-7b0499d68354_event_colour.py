"""event colour: the colour an event has in Google Calendar, so the pages draw it in that colour

Revision ID: 7b0499d68354
Revises: 5ace5678d3d9
Create Date: 2026-11-08 23:33:19.246853

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.core.db  # noqa: F401  custom column types (UTCDateTime) are written as app.core.db.X


# revision identifiers, used by Alembic.
revision: str = '7b0499d68354'
down_revision: Union[str, Sequence[str], None] = '5ace5678d3d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.add_column(sa.Column('color', sa.String(length=16), server_default='', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.drop_column('color')
