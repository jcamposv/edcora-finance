from logging.config import fileConfig
import os
import sys

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.core.database import Base
from app.models import *

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def get_url():
    """Get database URL from Railway environment variables or local config"""
    # Railway provides DATABASE_URL directly
    if os.getenv("DATABASE_URL") is not None:
        return os.getenv("DATABASE_URL")
    
    # Fallback to individual PostgreSQL environment variables
    user = os.getenv("PGUSER", "finanzas_user")
    password = os.getenv("PGPASSWORD", "finanzas_password") 
    host = os.getenv("PGHOST", "localhost")
    port = os.getenv("PGPORT", "5432")
    db = os.getenv("PGDATABASE", "finanzas_db")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"

# Set the database URL in the config
config.set_main_option("sqlalchemy.url", get_url())

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()