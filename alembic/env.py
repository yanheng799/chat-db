import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Ensure src/ is on sys.path so model imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from config.settings import Settings  # noqa: E402
from config.models import Base  # noqa: E402
import config.data_source_model  # noqa: F401 — register model for autogenerate

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = Settings()
db_url = (
    f"postgresql+psycopg2://{settings.postgres_user}"
    f":{settings.postgres_password}"
    f"@{settings.postgres_host}"
    f":{settings.postgres_port}"
    f"/{settings.postgres_db}"
)
config.set_main_option("sqlalchemy.url", db_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context_begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
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
