"""
Storage domain service - calculates storage usage by assignment, task, and orphaned data.
"""

import logging
from pathlib import Path

from constants import BUCKET_NAME
from shared.models import Assignment, File, PlagiarismTask, Subject
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class StorageService:
    def __init__(self, db: AsyncSession, s3_storage=None):
        self.db = db
        self.s3_storage = s3_storage

    async def get_storage_usage(self) -> dict:
        """
        Calculate storage usage broken down by:
        - Total usage
        - By assignment
        - Orphaned tasks
        - Redis cache estimate
        """
        total_size = 0
        by_assignment = []
        orphaned_size = 0

        query = (
            select(
                PlagiarismTask.id,
                PlagiarismTask.assignment_id,
                File.file_path,
                Assignment.name.label("assignment_name"),
                Subject.name.label("subject_name"),
            )
            .join(File, File.task_id == PlagiarismTask.id)
            .outerjoin(Assignment, PlagiarismTask.assignment_id == Assignment.id)
            .outerjoin(Subject, Assignment.subject_id == Subject.id)
            .where(PlagiarismTask.deleted_at.is_(None))
            .where(File.deleted_at.is_(None))
        )

        result = await self.db.execute(query)
        rows = result.all()

        assignment_sizes: dict[str, dict] = {}

        for row in rows:
            task_id = str(row[0])
            assignment_id = str(row[1]) if row[1] else None
            file_path = row[2]
            assignment_name = row[3]
            subject_name = row[4]

            file_size = 0
            try:
                path = Path(file_path)
                if path.exists():
                    file_size = path.stat().st_size
            except Exception:
                pass

            total_size += file_size

            if assignment_id:
                if assignment_id not in assignment_sizes:
                    assignment_sizes[assignment_id] = {
                        "assignment_id": assignment_id,
                        "assignment_name": assignment_name or "Unknown",
                        "subject_name": subject_name,
                        "size_bytes": 0,
                        "file_count": 0,
                    }
                assignment_sizes[assignment_id]["size_bytes"] += file_size
                assignment_sizes[assignment_id]["file_count"] += 1
            else:
                orphaned_size += file_size

        by_assignment = list(assignment_sizes.values())
        by_assignment.sort(key=lambda x: x["size_bytes"], reverse=True)

        redis_size = await self._estimate_redis_size()

        return {
            "total_bytes": total_size,
            "total_human": self._format_bytes(total_size),
            "by_assignment": [
                {
                    **item,
                    "size_human": self._format_bytes(item["size_bytes"]),
                    "percentage": round((item["size_bytes"] / total_size * 100), 1) if total_size > 0 else 0,
                }
                for item in by_assignment
            ],
            "orphaned_bytes": orphaned_size,
            "orphaned_human": self._format_bytes(orphaned_size),
            "orphaned_percentage": round((orphaned_size / total_size * 100), 1) if total_size > 0 else 0,
            "redis_bytes": redis_size,
            "redis_human": self._format_bytes(redis_size),
            "redis_percentage": round((redis_size / total_size * 100), 1) if total_size > 0 else 0,
        }

    async def get_assignment_storage_usage(self, assignment_id: str) -> dict:
        """
        Calculate storage usage for a specific assignment.
        """
        total_size = 0
        file_count = 0

        query = (
            select(File.file_path)
            .join(PlagiarismTask, File.task_id == PlagiarismTask.id)
            .where(PlagiarismTask.assignment_id == assignment_id)
            .where(PlagiarismTask.deleted_at.is_(None))
            .where(File.deleted_at.is_(None))
        )

        result = await self.db.execute(query)
        rows = result.all()

        for row in rows:
            file_path = row[0]
            try:
                path = Path(file_path)
                if path.exists():
                    total_size += path.stat().st_size
                    file_count += 1
            except Exception:
                pass

        return {
            "assignment_id": assignment_id,
            "total_bytes": total_size,
            "total_human": self._format_bytes(total_size),
            "file_count": file_count,
        }

    async def _estimate_redis_size(self) -> int:
        """Estimate Redis cache size by counting keys."""
        try:
            from config import settings
            import redis

            client = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                db=settings.redis_db,
                password=settings.redis_password or None,
            )

            fingerprint_keys = client.keys("fp:*")
            inverted_keys = client.keys("inv:*")
            total_keys = len(fingerprint_keys) + len(inverted_keys)

            client.close()

            return total_keys * 200
        except Exception as e:
            logger.warning("Failed to estimate Redis size: %s", e)
            return 0

    @staticmethod
    def _format_bytes(bytes_count: int) -> str:
        """Format bytes into human-readable string."""
        if bytes_count < 1024:
            return f"{bytes_count} B"
        elif bytes_count < 1024 * 1024:
            return f"{bytes_count / 1024:.1f} KB"
        elif bytes_count < 1024 * 1024 * 1024:
            return f"{bytes_count / (1024 * 1024):.1f} MB"
        else:
            return f"{bytes_count / (1024 * 1024 * 1024):.1f} GB"
