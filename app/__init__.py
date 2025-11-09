import os

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate


db = SQLAlchemy()
migrate = Migrate()


def create_app(test_config: dict | None = None) -> Flask:
    """Application factory for BehavMetrix."""
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "behavmetrix-secret"),
        SQLALCHEMY_DATABASE_URI=os.environ.get(
            "DATABASE_URL", f"sqlite:///{os.path.join(app.instance_path, 'behavmetrix.db')}"
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        UPLOAD_FOLDER=os.environ.get("UPLOAD_FOLDER", os.path.join(app.instance_path, "uploads")),
        MAX_CONTENT_LENGTH=16 * 1024 * 1024,
    )

    if test_config is not None:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)

    from .db_maintenance import ensure_minimum_schema  # noqa: WPS433

    with app.app_context():
        ensure_minimum_schema()

    from . import routes, api  # noqa: WPS433

    app.register_blueprint(routes.bp)
    app.register_blueprint(api.api_bp, url_prefix="/api")

    @app.cli.command("create-mock-data")
    def create_mock_data_command() -> None:
        """Populate the database with mock animals, behaviors, and logs."""
        from .mock_data import create_mock_data

        create_mock_data()
        print("Mock data created")

    return app
