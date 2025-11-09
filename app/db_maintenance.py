"""Utility helpers to keep the SQLite schema in sync with the models."""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError

from . import db


def ensure_columns(table: str, columns_sql: dict[str, str]) -> None:
    """Ensure each column in ``columns_sql`` exists on ``table``.

    Parameters
    ----------
    table:
        The table name to inspect.
    columns_sql:
        Mapping of column name -> SQL ``ALTER TABLE`` snippet to add it.
    """

    engine = db.get_engine()
    inspector = inspect(engine)

    try:
        if not inspector.has_table(table):  # legacy deployments might not have the table yet
            return
    except OperationalError:  # pragma: no cover - safety guard for engines that error on lookup
        return

    try:
        existing: set[str] = {column["name"] for column in inspector.get_columns(table)}
    except OperationalError:  # pragma: no cover - skip if the table appears during startup
        return
    except Exception:  # pragma: no cover - surface level guard for fresh DBs
        existing = set()

    missing = [name for name in columns_sql if name not in existing]
    if not missing:
        return

    with engine.connect() as connection:
        for name in missing:
            try:
                connection.execute(text(columns_sql[name]))
            except OperationalError:  # pragma: no cover - skip if column already exists mid-run
                continue
        connection.commit()


def ensure_minimum_schema() -> None:
    """Patch legacy SQLite databases with newly introduced columns."""

    ensure_columns(
        "behavior_logs",
        {
            "mode": "ALTER TABLE behavior_logs ADD COLUMN mode VARCHAR DEFAULT 'real_time'",
            "metadata": "ALTER TABLE behavior_logs ADD COLUMN metadata JSON",
        },
    )

    ensure_columns(
        "behavior_sessions",
        {
            "mode": "ALTER TABLE behavior_sessions ADD COLUMN mode VARCHAR DEFAULT 'real_time'",
            "metadata": "ALTER TABLE behavior_sessions ADD COLUMN metadata JSON",
        },
    )

    ensure_columns(
        "enrichment_logs",
        {
            "metadata": "ALTER TABLE enrichment_logs ADD COLUMN metadata JSON",
        },
    )
