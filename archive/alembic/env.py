"""
Alembic environment.

This file is invoked by `alembic upgrade head` (and friends). It is
NOT imported by the FastAPI app at runtime.

Key responsibilities:
1. Read DATABASE_PATH from the environment (same env var the FastAPI
   app uses, via app/config.py).
2. Build a SQLAlchemy URL pointing at that SQLite file.
3. Run the migration scripts in alembic/versions/ either offline
   (emit SQL) or online (apply to the DB).

We do NOT use SQLAlchemy ORM autogeneration here. Schema is hand-
written SQL in sql/initial_schema.sql, applied by migration 0001.
Future schema changes will be additional hand-written revisions.
"""

from logging.config import fileConfig
from pathlib import Path
import os

from alembic import context
from sqlalchemy import engine_from_config, pool


# Alembic Config object (alembic.ini contents)
config = context.config

# Apply logging config from alembic.ini if it specifies one.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _database_url() -> str:
    """
    Return the SQLAlchemy URL pointing at our SQLite file.

    Falls back to a sensible default if DATABASE_PATH is unset (e.g.,
    when running alembic locally without the container env).
    """
    db_path = os.environ.get("DATABASE_PATH", "/data/archive.db")
    # SQLite needs three slashes for absolute paths
    if not db_path.startswith("/"):
        # relative — resolve from this file's parent (archive/)
        db_path = str((Path(__file__).resolve().parent.parent / db_path).resolve())
    return f"sqlite:///{db_path}"


def run_migrations_offline() -> None:
    """Run migrations without an active DBAPI connection (emit SQL)."""
    url = _database_url()
    context.configure(
        url=url,
        target_metadata=None,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live DB connection."""
    # Inject the URL into the section that engine_from_config will read.
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = _database_url()

    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=None,
            # Important for SQLite to honor FK constraints during
            # migrations (default-off there).
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
