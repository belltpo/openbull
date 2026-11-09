from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import all models so metadata is populated
from backend.models import Base  # noqa: F401, E402
from backend.config import get_settings  # noqa: E402

target_metadata = Base.metadata


def _database_url() -> str:
    """Resolve the DSN from DATABASE_URL (.env), not from alembic.ini.

    alembic.ini is tracked in git, so any DSN written there is published with
    the repository — it used to carry postgres:123456. .env is gitignored and
    already holds the real credentials.

    No fallback to the ini value: the `backend.models` import above needs the
    app settings anyway, so alembic cannot run without DATABASE_URL set. The
    ini key is retained only because alembic requires it to be present.
    """
    return get_settings().sync_database_url


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(), target_metadata=target_metadata, literal_binds=True
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
