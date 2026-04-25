"""
Alembic environment configuration.

Sets up the migration environment with the correct metadata from shared models.
"""

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# Try to find src directory - either in project root or directly in /app
src_path = (
    os.path.join(project_root, "src")
    if os.path.exists(os.path.join(project_root, "src"))
    else project_root
)

if project_root not in sys.path:
    sys.path.insert(0, project_root)
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Import models
from pydantic import Field  # noqa: E402

# Load database config directly without full application config
from pydantic_settings import BaseSettings  # noqa: E402
from shared.models import SharedBase  # noqa: E402


class DatabaseConfig(BaseSettings):
    host: str = Field(default="localhost", validation_alias="DB_HOST")
    port: int = Field(default=5432, validation_alias="DB_PORT")
    name: str = Field(default="plagiarism_db", validation_alias="DB_NAME")
    user: str = Field(default="plagiarism_user", validation_alias="DB_USER")
    password: str = Field(default="", validation_alias="DB_PASS")

    model_config = {
        "env_prefix": "",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


db_config = DatabaseConfig()

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set database connection settings in alembic.ini
section = config.config_ini_section
config.set_section_option(section, "DB_HOST", db_config.host)
config.set_section_option(section, "DB_PORT", str(db_config.port))
config.set_section_option(section, "DB_USER", db_config.user)
config.set_section_option(section, "DB_NAME", db_config.name)
config.set_section_option(section, "DB_PASS", db_config.password)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = SharedBase.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
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
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
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
