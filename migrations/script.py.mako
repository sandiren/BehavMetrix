<%text>
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
</%text>

from alembic import op
import sqlalchemy as sa
% if imports:
${imports}
% endif


def upgrade() -> None:
% if upgrades:
${upgrades}
% else:
    pass
% endif


def downgrade() -> None:
% if downgrades:
${downgrades}
% else:
    pass
% endif
