"""
Subject access service for managing user-subject permissions.
"""

import logging
import uuid
from datetime import UTC, datetime
from uuid import uuid4

from shared.models import SubjectAccess
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

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
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                # Race: another concurrent grant_access won. Return the existing row.
                result = await session.execute(
                    select(SubjectAccess).where(
                        SubjectAccess.user_id == user_uuid,
                        SubjectAccess.subject_id == subject_uuid,
                    )
                )
                winner = result.scalar_one_or_none()
                if winner is None:
                    raise
                logger.info(
                    f"Concurrent grant race for user {user_id} -> subject {subject_id}; "
                    "returning existing row"
                )
                return winner
            await session.refresh(access)

            logger.info(f"Granted subject access: user {user_id} -> subject {subject_id}")
            return access

    @staticmethod
    async def revoke_access(user_id: str, subject_id: str) -> bool:
        """
        Revoke a user's access to a subject.
        Returns True if revoked, False if no access existed.
        """
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

            logger.info(f"Revoked subject access: user {user_id} from subject {subject_id}")
            return True

    @staticmethod
    async def has_access(user_id: str, subject_id: str) -> bool:
        """
        Check if a user has access to a subject.
        """
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
    async def get_accessible_assignment_ids(db, user_id: str) -> list[str]:
        """
        Get list of assignment IDs a user has access to via their subjects.

        Uses the provided database session (no new connection) so it participates
        in the caller's transaction/connection.

        Returns an empty list if the user has no subject access (caller can use
        this to short-circuit queries). Returns an empty list for invalid user IDs.
        """
        try:
            user_uuid = uuid.UUID(user_id)
        except ValueError:
            return []

        from shared.models import Assignment

        result = await db.execute(
            select(Assignment.id)
            .join(SubjectAccess, SubjectAccess.subject_id == Assignment.subject_id)
            .where(SubjectAccess.user_id == user_uuid)
            .where(Assignment.deleted_at.is_(None))
        )
        return [str(row[0]) for row in result.all()]

    @staticmethod
    async def get_subject_members(subject_id: str) -> list[dict]:
        """
        Get all members of a subject with their details.
        """
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
