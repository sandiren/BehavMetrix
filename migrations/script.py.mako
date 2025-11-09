<%text>
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
</%text>
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
<% if imports: %>
${imports}
<% endif %>

# revision identifiers, used by Alembic.
revision = '${up_revision}'
down_revision = ${down_revision | repr}
branch_labels = ${branch_labels | repr}
depends_on = ${depends_on | repr}


def upgrade() -> None:
<% if upgrades: %>
${upgrades}
<% else: %>
    pass
<% endif %>


def downgrade() -> None:
<% if downgrades: %>
${downgrades}
<% else: %>
    pass
<% endif %>
