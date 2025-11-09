"""Database maintenance helpers for BehavMetrix."""

from __future__ import annotations

from typing import Mapping

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection, Engine

from . import db


_BEHAVIOR_DEFINITION_PATCHES: Mapping[str, str] = {
    "default_duration_seconds": "INTEGER",
    "keyboard_shortcut": "VARCHAR(32)",
}


def _apply_column_patch(connection: Connection, table: str, column: str, ddl: str) -> None:
    """Add a column to a table if it does not already exist."""
    inspector = inspect(connection)
    if table not in inspector.get_table_names():
        return

    existing_columns = {col["name"] for col in inspector.get_columns(table)}
    if column not in existing_columns:
        connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))


def ensure_minimum_schema() -> None:
    """Ensure runtime patches that keep legacy SQLite schemas usable are applied."""
    db.create_all()

    engine: Engine = db.engine
    with engine.begin() as connection:
        for column, ddl in _BEHAVIOR_DEFINITION_PATCHES.items():
            _apply_column_patch(connection, "behavior_definitions", column, ddl)
