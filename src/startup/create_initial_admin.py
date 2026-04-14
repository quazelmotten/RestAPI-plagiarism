"""
Create initial admin user on startup.
"""

import logging
import os

from sqlalchemy import select

from auth.models import User
from auth.password_validation import validate_password
from auth.service import get_password_hash
from database import async_session_maker

logger = logging.getLogger(__name__)


async def create_initial_admin():
    """
    Create initial admin user from environment variables on startup.
    Only runs if no users exist in the database.
    """
    email = os.getenv("INITIAL_ADMIN_EMAIL")
    password = os.getenv("INITIAL_ADMIN_PASSWORD")

    if not email or not password:
        logger.info(
            "INITIAL_ADMIN_EMAIL or INITIAL_ADMIN_PASSWORD not set, skipping initial admin creation"
        )
        return

    # Validate password
    validation_errors = validate_password(password)
    if validation_errors:
        logger.error(
            f"Initial admin password does not meet requirements: {', '.join(validation_errors)}"
        )
        return

    async with async_session_maker() as session:
        # Check if any users exist
        result = await session.execute(select(User))
        existing_users = result.scalars().first()

        if existing_users:
            logger.info("Users already exist, skipping initial admin creation")
            return

        # Check if admin with this email already exists
        result = await session.execute(select(User).where(User.email == email))
        existing_admin = result.scalar_one_or_none()

        if existing_admin:
            logger.info(f"Admin user {email} already exists")
            return

        # Create initial admin
        admin = User(
            email=email,
            hashed_password=get_password_hash(password),
            is_global_admin=True,
        )
        session.add(admin)
        await session.commit()

        logger.info(f"Initial admin user created: {email}")
