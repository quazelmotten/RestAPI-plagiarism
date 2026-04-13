"""
Subject access service for managing user-subject permissions.
"""

import logging
from datetime import UTC, datetime
from uuid import uuid4

from shared.models import SubjectAccess
from sqlalchemy import select

from auth.models import User
from database import async_session_maker

logger = logging.getLogger(__name__)


class SubjectAccessService:
    """Service for managing subject access permissions."""

    @staticmethod
    async def grant_access(
        user_id: str, subject_id: str, granted_by: str | None = None
    ) -> SubjectAccess:
        """
        Grant a user access to a subject.
        """
        import uuid

        async with async_session_maker() as session:
            # Convert IDs to UUID for proper comparison
            try:
                user_uuid = uuid.UUID(user_id)
                subject_uuid = uuid.UUID(subject_id)
                granted_by_uuid = uuid.UUID(granted_by) if granted_by else None
            except ValueError as e:
                raise ValueError(f"Invalid UUID format: {e}") from e

            # Check if access already exists
            result = await session.execute(
                select(SubjectAccess).where(
                    SubjectAccess.user_id == user_uuid, SubjectAccess.subject_id == subject_uuid
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                logger.warning(f"User {user_id} already has access to subject {subject_id}")
                return existing

            access = SubjectAccess(
                id=str(uuid4()),
                user_id=user_uuid,
                subject_id=subject_uuid,
                granted_by=granted_by_uuid,
                granted_at=datetime.now(UTC),
            )
            session.add(access)
            await session.commit()
            await session.refresh(access)

            logger.info(f"Granted subject access: user {user_id} -> subject {subject_id}")
            return access

    @staticmethod
    async def revoke_access(user_id: str, subject_id: str) -> bool:
        """
        Revoke a user's access to a subject.
        Returns True if revoked, False if no access existed.
        """
        import uuid

        async with async_session_maker() as session:
            # Convert IDs to UUID for proper comparison
            try:
                user_uuid = uuid.UUID(user_id)
                subject_uuid = uuid.UUID(subject_id)
            except ValueError:
                return False

            result = await session.execute(
                select(SubjectAccess).where(
                    SubjectAccess.user_id == user_uuid, SubjectAccess.subject_id == subject_uuid
                )
            )
            access = result.scalar_one_or_none()

            if not access:
                return False

            await session.delete(access)
            await session.commit()

            logger.info(f"Revoked subject access: user {user_id} -> subject {subject_id}")
            return True

    @staticmethod
    async def has_access(user_id: str, subject_id: str) -> bool:
        """
        Check if a user has access to a subject.
        """
        import uuid

        async with async_session_maker() as session:
            # Convert IDs to UUID for proper comparison
            try:
                user_uuid = uuid.UUID(user_id)
                subject_uuid = uuid.UUID(subject_id)
            except ValueError:
                return False

            result = await session.execute(
                select(SubjectAccess).where(
                    SubjectAccess.user_id == user_uuid, SubjectAccess.subject_id == subject_uuid
                )
            )
            return result.scalar_one_or_none() is not None

    @staticmethod
    async def get_user_subjects(user_id: str) -> list[str]:
        """
        Get list of subject IDs a user has access to.
        """
        import uuid

        async with async_session_maker() as session:
            # Convert user ID to UUID for proper comparison
            try:
                user_uuid = uuid.UUID(user_id)
            except ValueError:
                return []

            result = await session.execute(
                select(SubjectAccess.subject_id).where(SubjectAccess.user_id == user_uuid)
            )
            return [str(row[0]) for row in result.all()]

    @staticmethod
    async def get_subject_members(subject_id: str) -> list[dict]:
        """
        Get all members of a subject with their details.
        """
        import uuid

        async with async_session_maker() as session:
            # Convert subject_id to UUID for proper comparison
            try:
                subject_uuid = uuid.UUID(subject_id)
            except ValueError:
                return []

            result = await session.execute(
                select(SubjectAccess, User)
                .join(User, SubjectAccess.user_id == User.id)
                .where(SubjectAccess.subject_id == subject_uuid)
            )
            members = []
            for access, user in result:
                members.append(
                    {
                        "user_id": str(user.id),
                        "email": user.email,
                        "granted_at": access.granted_at,
                        "granted_by": str(access.granted_by) if access.granted_by else None,
                    }
                )
            return members

    @staticmethod
    async def can_manage_subject(user: User, subject_id: str) -> bool:
        """
        Check if user can manage (admin) a subject.
        Global admins can manage any subject.
        Regular users must have subject access.
        """
        # Global admins can manage everything
        if user.is_global_admin:
            return True

        # Check if user has access to this subject
        return await SubjectAccessService.has_access(str(user.id), subject_id)
