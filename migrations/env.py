import os

from alembic import context
from sqlalchemy import create_engine, pool
from sqlalchemy.engine import Connection, make_url


def run_migrations(connection: Connection) -> None:
    """Run tracked SQL migrations in a single transaction."""
    context.configure(connection=connection, target_metadata=None)
    with context.begin_transaction():
        context.run_migrations()


def main() -> None:
    """Use an injected connection or explicit PostgreSQL URL."""
    connection = context.config.attributes.get("connection")
    if connection is not None:
        run_migrations(connection)
        return

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set to run migrations")
    if make_url(database_url).get_backend_name() != "postgresql":
        raise RuntimeError("Migrations require PostgreSQL")

    if context.is_offline_mode():
        context.configure(
            url=database_url,
            target_metadata=None,
            literal_binds=True,
            dialect_opts={"paramstyle": "named"},
        )
        with context.begin_transaction():
            context.run_migrations()
        return

    engine = create_engine(
        database_url, poolclass=pool.NullPool, hide_parameters=True
    )
    try:
        with engine.connect() as db_connection:
            run_migrations(db_connection)
    finally:
        engine.dispose()


main()
