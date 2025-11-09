"""Alembic environment configuration for BehavMetrix."""

from __future__ import annotations

import logging
import os
from logging.config import fileConfig

from alembic import context
from flask import current_app

logger = logging.getLogger(__name__)

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

config_file_name = config.config_file_name
if config_file_name and os.path.exists(config_file_name):
    fileConfig(config_file_name)
else:
    logger.debug(
        "Alembic configuration file %s is missing; skipping logging setup.",
        config_file_name,
    )

# interpret the config file for Python logging.
# this line sets up loggers basically.
# target_metadata points to the metadata for 'autogenerate' support.
target_metadata = current_app.extensions["migrate"].db.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = current_app.extensions["migrate"].db.get_engine().url
    context.configure(
        url=str(url),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = current_app.extensions["migrate"].db.engine

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
