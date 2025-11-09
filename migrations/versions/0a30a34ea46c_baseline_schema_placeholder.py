"""Placeholder for legacy base schema revision.

This repository historically started from Alembic revision 0a30a34ea46c,
which was applied in production deployments outside of version control.
To allow new revisions to build on top of existing databases, we provide a
no-op migration that simply anchors the revision history so Alembic can
resolve dependencies without errors.
"""

from __future__ import annotations

# revision identifiers, used by Alembic.
revision = "0a30a34ea46c"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Legacy databases already contain the base schema."""
    # This placeholder intentionally performs no operations.
    pass


def downgrade() -> None:
    """Downgrading from the base placeholder has no effect."""
    pass
