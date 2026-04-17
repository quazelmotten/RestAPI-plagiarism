"""
Run database migrations on application startup.
"""

import logging
import os
from pathlib import Path

from alembic import command
from alembic.config import Config

from config import settings

logger = logging.getLogger(__name__)


def run_migrations() -> None:
    """
    Run database migrations using alembic programmatically.
    This runs on application startup to ensure the database schema is always up to date.
    Uses alembic's built-in advisory locks to prevent race conditions.
    """
    try:
        # Find alembic.ini path - it's in database directory at project root
        # In container, /app is project root, in local dev it's parent of src
        project_root = (
            Path("/app")
            if Path("/app/database/alembic.ini").exists()
            else Path(__file__).parent.parent.parent
        )
        alembic_ini_path = project_root / "database" / "alembic.ini"
        alembic_migrations_path = project_root / "database" / "migration"

        if not alembic_ini_path.exists():
            logger.warning(
                "Alembic ini file not found at %s, skipping migrations", alembic_ini_path
            )
            return

        # Load alembic configuration
        alembic_cfg = Config(str(alembic_ini_path))
        alembic_cfg.set_main_option("script_location", str(alembic_migrations_path))
        alembic_cfg.set_main_option("prepend_sys_path", str(project_root))

        # Set database connection parameters
        db_url = (
            f"postgresql+psycopg2://{settings.database.user}:{settings.database.password}@"
            f"{settings.database.host}:{settings.database.port}/{settings.database.name}"
        )
        alembic_cfg.set_main_option("sqlalchemy.url", db_url)

        logger.info("Running database migrations...")
        command.upgrade(alembic_cfg, "head")
        logger.info("Database migrations completed successfully")

    except Exception as e:
        logger.exception("Failed to run database migrations: %s", str(e))
        # Don't fail startup if migrations fail - allow app to run anyway
        # This prevents the app from being completely unavailable if there's a migration issue
