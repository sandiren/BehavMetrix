"""Add session_id and new fields to behavior_logs"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "d7fed5ad1ad5"
down_revision = "0a30a34ea46c"
branch_labels = None
depends_on = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column_name in {col["name"] for col in inspector.get_columns(table_name)}


def _foreign_key_exists(table_name: str, constraint_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(fk["name"] == constraint_name for fk in inspector.get_foreign_keys(table_name))


def upgrade() -> None:
    with op.batch_alter_table("behavior_logs", schema=None) as batch_op:
        if not _column_exists("behavior_logs", "sample_type"):
            batch_op.add_column(sa.Column("sample_type", sa.String(), nullable=True, server_default="focal"))
        if not _column_exists("behavior_logs", "mode"):
            batch_op.add_column(sa.Column("mode", sa.String(), nullable=True, server_default="real_time"))
        if not _column_exists("behavior_logs", "intensity"):
            batch_op.add_column(sa.Column("intensity", sa.Integer(), nullable=True))
        if not _column_exists("behavior_logs", "duration_seconds"):
            batch_op.add_column(sa.Column("duration_seconds", sa.Float(), nullable=True))
        if not _column_exists("behavior_logs", "metadata"):
            batch_op.add_column(sa.Column("metadata", sa.JSON(), nullable=True))
        if not _column_exists("behavior_logs", "session_id"):
            batch_op.add_column(sa.Column("session_id", sa.Integer(), nullable=True))
        if not _column_exists("behavior_logs", "interaction_partner_id"):
            batch_op.add_column(sa.Column("interaction_partner_id", sa.Integer(), nullable=True))

        if not _foreign_key_exists(
            "behavior_logs", "fk_behavior_logs_session_id_behavior_sessions"
        ):
            batch_op.create_foreign_key(
                "fk_behavior_logs_session_id_behavior_sessions",
                "behavior_sessions",
                ["session_id"],
                ["id"],
            )
        if not _foreign_key_exists(
            "behavior_logs", "fk_behavior_logs_interaction_partner_id_animals"
        ):
            batch_op.create_foreign_key(
                "fk_behavior_logs_interaction_partner_id_animals",
                "animals",
                ["interaction_partner_id"],
                ["id"],
            )

    with op.batch_alter_table("behavior_sessions", schema=None) as batch_op:
        if not _column_exists("behavior_sessions", "mode"):
            batch_op.add_column(sa.Column("mode", sa.String(), nullable=True, server_default="real_time"))
        if not _column_exists("behavior_sessions", "metadata"):
            batch_op.add_column(sa.Column("metadata", sa.JSON(), nullable=True))

    with op.batch_alter_table("enrichment_logs", schema=None) as batch_op:
        if not _column_exists("enrichment_logs", "start_time"):
            batch_op.add_column(sa.Column("start_time", sa.DateTime(), nullable=True))
        if not _column_exists("enrichment_logs", "end_time"):
            batch_op.add_column(sa.Column("end_time", sa.DateTime(), nullable=True))
        if not _column_exists("enrichment_logs", "duration_minutes"):
            batch_op.add_column(sa.Column("duration_minutes", sa.Float(), nullable=True))
        if not _column_exists("enrichment_logs", "response"):
            batch_op.add_column(sa.Column("response", sa.String(), nullable=True))
        if not _column_exists("enrichment_logs", "outcome"):
            batch_op.add_column(sa.Column("outcome", sa.String(), nullable=True))
        if not _column_exists("enrichment_logs", "notes"):
            batch_op.add_column(sa.Column("notes", sa.Text(), nullable=True))
        if not _column_exists("enrichment_logs", "tag"):
            batch_op.add_column(sa.Column("tag", sa.String(), nullable=True))
        if not _column_exists("enrichment_logs", "frequency"):
            batch_op.add_column(sa.Column("frequency", sa.String(), nullable=True))
        if not _column_exists("enrichment_logs", "metadata"):
            batch_op.add_column(sa.Column("metadata", sa.JSON(), nullable=True))

    with op.batch_alter_table("behavior_definitions", schema=None) as batch_op:
        if not _column_exists("behavior_definitions", "is_dyadic"):
            batch_op.add_column(sa.Column("is_dyadic", sa.Boolean(), nullable=True, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table("behavior_definitions", schema=None) as batch_op:
        if _column_exists("behavior_definitions", "is_dyadic"):
            batch_op.drop_column("is_dyadic")

    with op.batch_alter_table("enrichment_logs", schema=None) as batch_op:
        if _column_exists("enrichment_logs", "metadata"):
            batch_op.drop_column("metadata")
        if _column_exists("enrichment_logs", "frequency"):
            batch_op.drop_column("frequency")
        if _column_exists("enrichment_logs", "tag"):
            batch_op.drop_column("tag")
        if _column_exists("enrichment_logs", "notes"):
            batch_op.drop_column("notes")
        if _column_exists("enrichment_logs", "outcome"):
            batch_op.drop_column("outcome")
        if _column_exists("enrichment_logs", "response"):
            batch_op.drop_column("response")
        if _column_exists("enrichment_logs", "duration_minutes"):
            batch_op.drop_column("duration_minutes")
        if _column_exists("enrichment_logs", "end_time"):
            batch_op.drop_column("end_time")
        if _column_exists("enrichment_logs", "start_time"):
            batch_op.drop_column("start_time")

    with op.batch_alter_table("behavior_sessions", schema=None) as batch_op:
        if _column_exists("behavior_sessions", "metadata"):
            batch_op.drop_column("metadata")
        if _column_exists("behavior_sessions", "mode"):
            batch_op.drop_column("mode")

    with op.batch_alter_table("behavior_logs", schema=None) as batch_op:
        if _foreign_key_exists(
            "behavior_logs", "fk_behavior_logs_interaction_partner_id_animals"
        ):
            batch_op.drop_constraint(
                "fk_behavior_logs_interaction_partner_id_animals",
                type_="foreignkey",
            )
        if _foreign_key_exists(
            "behavior_logs", "fk_behavior_logs_session_id_behavior_sessions"
        ):
            batch_op.drop_constraint(
                "fk_behavior_logs_session_id_behavior_sessions",
                type_="foreignkey",
            )

        if _column_exists("behavior_logs", "interaction_partner_id"):
            batch_op.drop_column("interaction_partner_id")
        if _column_exists("behavior_logs", "session_id"):
            batch_op.drop_column("session_id")
        if _column_exists("behavior_logs", "metadata"):
            batch_op.drop_column("metadata")
        if _column_exists("behavior_logs", "duration_seconds"):
            batch_op.drop_column("duration_seconds")
        if _column_exists("behavior_logs", "intensity"):
            batch_op.drop_column("intensity")
        if _column_exists("behavior_logs", "mode"):
            batch_op.drop_column("mode")
        if _column_exists("behavior_logs", "sample_type"):
            batch_op.drop_column("sample_type")
