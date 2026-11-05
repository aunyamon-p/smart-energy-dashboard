"""Create the initial application schema.

The model metadata is used only for this initial, additive bootstrap. Future
schema changes must be represented by new Alembic revisions.
"""

from alembic import op

from backend.app.db import Base
from backend.app import models  # noqa: F401

revision = "20261105_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind, checkfirst=True)
