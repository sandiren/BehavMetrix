"""Initial tables"""

from __future__ import annotations

revision = "0a30a34ea46c"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app import create_app, db

    app = create_app()
    with app.app_context():
        db.create_all()


def downgrade() -> None:
    from app import create_app, db

    app = create_app()
    with app.app_context():
        db.drop_all()
