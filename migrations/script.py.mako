<%text>
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
</%text>

from alembic import op
import sqlalchemy as sa
${imports if imports}


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
