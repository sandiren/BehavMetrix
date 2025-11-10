"""Rename EthogramVersion to Ethogram and add name column

Revision ID: 9768dcb564ac
Revises: eb0872492d4e
Create Date: 2025-11-10 14:43:44.223136

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9768dcb564ac'
down_revision: Union[str, Sequence[str], None] = 'eb0872492d4e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.rename_table('ethogram_versions', 'ethograms')
    op.add_column('ethograms', sa.Column('name', sa.String(), nullable=True))
    op.alter_column('ethograms', 'version_label', new_column_name='version')
    op.alter_column('behavior_definitions', 'ethogram_id', new_column_name='ethogram_id')
    op.alter_column('observation_sessions', 'ethogram_version_id', new_column_name='ethogram_id')


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('observation_sessions', 'ethogram_id', new_column_name='ethogram_version_id')
    op.alter_column('behavior_definitions', 'ethogram_id', new_column_name='ethogram_id')
    op.alter_column('ethograms', 'version', new_column_name='version_label')
    op.drop_column('ethograms', 'name')
    op.rename_table('ethograms', 'ethogram_versions')
