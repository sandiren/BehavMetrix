"""Conditionally add behavior definition metadata columns."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.exc import NoSuchTableError

# revision identifiers, used by Alembic.
revision = "d7fed5ad1ad5"
down_revision = None
branch_labels = None
depends_on = None


_BEHAVIOR_DEFINITION_COLUMNS = {
    "default_duration_seconds": sa.Column("default_duration_seconds", sa.Integer()),
    "keyboard_shortcut": sa.Column("keyboard_shortcut", sa.String(length=32)),
}


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    try:
        columns = {col["name"] for col in inspector.get_columns(table_name)}
    except NoSuchTableError:
        return False
    return column_name in columns


def upgrade() -> None:
    for column_name, column in _BEHAVIOR_DEFINITION_COLUMNS.items():
        if not _has_column("behavior_definitions", column_name):
            op.add_column("behavior_definitions", column.copy())


def downgrade() -> None:
    for column_name in _BEHAVIOR_DEFINITION_COLUMNS:
        if _has_column("behavior_definitions", column_name):
            op.drop_column("behavior_definitions", column_name)
