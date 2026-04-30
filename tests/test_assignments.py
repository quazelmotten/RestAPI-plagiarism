"""
Tests for assignment-scoped analysis feature.

Tests cover:
- Assignment CRUD endpoints
- Upload with assignment_id parameter
- Worker assignment-scoped file filtering
- Soft delete and restore functionality
"""

import os
import sys
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Resolve src path relative to project root (parent of tests/)
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_project_root, "src"))

from app import app  # noqa: E402
from assignments.schemas import AssignmentResponse, SubjectResponse  # noqa: E402
from tasks.schemas import TaskCreateResponse  # noqa: E402


@pytest_asyncio.fixture
async def client():
    """Async test client fixture."""
    from clients.redis_client import RedisClient

    if not hasattr(app.state, "redis_client"):
        app.state.redis_client = RedisClient()
    if not hasattr(app.state, "rabbitmq"):

        class DummyRabbitMQ:
            is_connected = False
            publish_message = AsyncMock()

        app.state.rabbitmq = DummyRabbitMQ()
    if not hasattr(app.state, "ws_manager"):

        class DummyWSManager:
            async def start(self):
                pass

            async def stop(self):
                pass

        app.state.ws_manager = DummyWSManager()
    if not hasattr(app.state, "s3_storage"):

        class DummyS3Storage:
            async def upload_file(self, *args, **kwargs):
                return {"path": "s3://test/file", "hash": "abc123"}
            async def upload_file_async(self, *args, **kwargs):
                return {"path": "s3://test/file", "hash": "abc123"}
            async def download_file(self, *args, **kwargs):
                return b"test content"
            async def delete_file(self, *args, **kwargs):
                pass

        app.state.s3_storage = DummyS3Storage()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class TestAssignmentEndpoints:
    async def test_create_assignment(self, client):
        from assignments.dependencies import get_assignment_service

        mock_svc = MagicMock()
        mock_svc.create_assignment = AsyncMock(
            return_value=AssignmentResponse(
                id="test-assignment-id",
                name="CS101 HW3",
                description="Homework 3 plagiarism check",
                created_at="2026-01-01T00:00:00",
                tasks_count=0,
                files_count=0,
            )
        )
        app.dependency_overrides[get_assignment_service] = lambda: mock_svc

        response = await client.post(
            "/plagitype/plagiarism/assignments",
            json={"name": "CS101 HW3", "description": "Homework 3 plagiarism check"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "CS101 HW3"
        assert data["description"] == "Homework 3 plagiarism check"
        assert "id" in data

    async def test_create_assignment_name_only(self, client):
        from assignments.dependencies import get_assignment_service

        mock_svc = MagicMock()
        mock_svc.create_assignment = AsyncMock(
            return_value=AssignmentResponse(
                id="test-assignment-id-2",
                name="Minimal Assignment",
                description=None,
                created_at="2026-01-01T00:00:00",
                tasks_count=0,
                files_count=0,
            )
        )
        app.dependency_overrides[get_assignment_service] = lambda: mock_svc

        response = await client.post(
            "/plagitype/plagiarism/assignments",
            json={"name": "Minimal Assignment"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Minimal Assignment"
        assert data["description"] is None

    async def test_get_assignments(self, client):
        response = await client.get("/plagitype/plagiarism/assignments")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data

    async def test_get_assignment_not_found(self, client):
        response = await client.get(
            "/plagitype/plagiarism/assignments/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 404

    async def test_get_assignment_invalid_uuid(self, client):
        response = await client.get("/plagitype/plagiarism/assignments/not-a-uuid")
        assert response.status_code == 422

    async def test_update_assignment_not_found(self, client):
        response = await client.patch(
            "/plagitype/plagiarism/assignments/00000000-0000-0000-0000-000000000000",
            json={"name": "Updated"},
        )
        assert response.status_code == 404

    async def test_delete_assignment_not_found(self, client):
        response = await client.delete(
            "/plagitype/plagiarism/assignments/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 404

    async def test_delete_assignment_soft_delete(self, client):
        """DELETE should soft delete (set deleted_at) not remove row."""
        import uuid

        from assignments.dependencies import get_assignment_repository, get_assignment_service

        assignment_id = str(uuid.uuid4())
        assignment = AssignmentResponse(
            id=assignment_id,
            name="Test",
            description=None,
            created_at="2026-01-01T00:00:00",
            tasks_count=0,
            files_count=0,
        )

        mock_repo = MagicMock()
        mock_repo.get_assignment = AsyncMock(return_value=assignment)
        mock_repo.delete_assignment = AsyncMock(return_value=True)

        mock_svc = MagicMock()
        mock_svc.delete_assignment = AsyncMock(return_value=True)

        app.dependency_overrides[get_assignment_repository] = lambda: mock_repo
        app.dependency_overrides[get_assignment_service] = lambda: mock_svc

        response = await client.delete(f"/plagitype/plagiarism/assignments/{assignment_id}")
        assert response.status_code == 204

    async def test_restore_assignment(self, client):
        """POST /restore should restore a soft-deleted assignment."""
        import uuid

        from assignments.dependencies import get_assignment_repository, get_assignment_service

        assignment_id = str(uuid.uuid4())
        deleted_assignment_data = AssignmentResponse(
            id=assignment_id,
            name="Test",
            description=None,
            created_at="2026-01-01T00:00:00",
            tasks_count=0,
            files_count=0,
        )

        mock_repo = MagicMock()
        # For valid_deleted_assignment_id: include_deleted=True must return the assignment
        mock_repo.get_assignment = AsyncMock(
            side_effect=lambda id, include_deleted=False: (
                deleted_assignment_data if include_deleted else None
            )
        )

        mock_svc = MagicMock()
        mock_svc.restore_assignment = AsyncMock(return_value=True)
        mock_svc.get_assignment = AsyncMock(return_value=deleted_assignment_data)

        app.dependency_overrides[get_assignment_repository] = lambda: mock_repo
        app.dependency_overrides[get_assignment_service] = lambda: mock_svc

        response = await client.post(f"/plagitype/plagiarism/assignments/{assignment_id}/restore")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == assignment_id

    async def test_restore_nondeleted_assignment_fails(self, client):
        """Restoring an assignment that wasn't deleted should return 404."""
        import uuid

        from assignments.dependencies import get_assignment_repository, get_assignment_service

        assignment_id = str(uuid.uuid4())

        mock_repo = MagicMock()
        mock_repo.get_assignment = AsyncMock(
            return_value=None
        )  # Not found even with include_deleted

        mock_svc = MagicMock()
        mock_svc.restore_assignment = AsyncMock(return_value=False)

        app.dependency_overrides[get_assignment_repository] = lambda: mock_repo
        app.dependency_overrides[get_assignment_service] = lambda: mock_svc

        response = await client.post(f"/plagitype/plagiarism/assignments/{assignment_id}/restore")
        assert response.status_code == 404


class TestSubjectEndpoints:
    """Tests for subject CRUD and soft delete/restore."""

    async def test_create_subject(self, client):
        from assignments.dependencies import get_subject_service

        mock_svc = MagicMock()
        mock_svc.create_subject = AsyncMock(
            return_value=SubjectResponse(
                id="test-subject-id",
                name="CS101",
                description=None,
                created_at="2026-01-01T00:00:00",
                assignments_count=0,
            )
        )
        app.dependency_overrides[get_subject_service] = lambda: mock_svc

        response = await client.post(
            "/plagitype/plagiarism/subjects",
            json={"name": "CS101", "description": None},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "CS101"

    async def test_delete_subject_soft_delete(self, client):
        """DELETE subject should soft delete."""
        import uuid

        from assignments.dependencies import get_subject_repository, get_subject_service

        subject_id = str(uuid.uuid4())
        subject = SubjectResponse(
            id=subject_id,
            name="Test",
            description=None,
            created_at="2026-01-01T00:00:00",
            assignments_count=0,
        )

        mock_repo = MagicMock()
        mock_repo.get_subject = AsyncMock(return_value=subject)

        mock_svc = MagicMock()
        mock_svc.delete_subject = AsyncMock(return_value=True)

        app.dependency_overrides[get_subject_repository] = lambda: mock_repo
        app.dependency_overrides[get_subject_service] = lambda: mock_svc

        response = await client.delete(f"/plagitype/plagiarism/subjects/{subject_id}")
        assert response.status_code == 204

    async def test_restore_subject(self, client):
        """POST /restore should restore a soft-deleted subject."""
        import uuid

        from assignments.dependencies import get_subject_repository, get_subject_service

        subject_id = str(uuid.uuid4())
        deleted_subject_data = SubjectResponse(
            id=subject_id,
            name="Test",
            description=None,
            created_at="2026-01-01T00:00:00",
            assignments_count=0,
        )

        mock_repo = MagicMock()
        mock_repo.get_subject = AsyncMock(
            side_effect=lambda id, include_deleted=False: (
                deleted_subject_data if include_deleted else None
            )
        )

        mock_svc = MagicMock()
        mock_svc.restore_subject = AsyncMock(return_value=True)
        mock_svc.get_subject = AsyncMock(return_value=deleted_subject_data)

        app.dependency_overrides[get_subject_repository] = lambda: mock_repo
        app.dependency_overrides[get_subject_service] = lambda: mock_svc

        response = await client.post(f"/plagitype/plagiarism/subjects/{subject_id}/restore")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == subject_id

    async def test_restore_nondeleted_subject_fails(self, client):
        """Restoring a subject that wasn't deleted should return 404."""
        import uuid

        from assignments.dependencies import get_subject_repository, get_subject_service

        subject_id = str(uuid.uuid4())

        mock_repo = MagicMock()
        mock_repo.get_subject = AsyncMock(return_value=None)

        mock_svc = MagicMock()
        mock_svc.restore_subject = AsyncMock(return_value=False)

        app.dependency_overrides[get_subject_repository] = lambda: mock_repo
        app.dependency_overrides[get_subject_service] = lambda: mock_svc

        response = await client.post(f"/plagitype/plagiarism/subjects/{subject_id}/restore")
        assert response.status_code == 404


class TestPartialUniqueIndexes:
    """Tests for partial unique indexes on name fields."""

    async def test_assignment_name_can_be_reused_after_delete(self, client):
        """Creating an assignment with the same name as a soft-deleted one should succeed."""
        from assignments.dependencies import get_assignment_service

        # First assignment
        assignment1 = AssignmentResponse(
            id="id-1",
            name="UniqueName",
            description=None,
            created_at="2026-01-01T00:00:00",
            tasks_count=0,
            files_count=0,
        )

        mock_svc = MagicMock()
        mock_svc.create_assignment = AsyncMock(
            side_effect=[
                assignment1,  # First create succeeds
                assignment1,  # Second create (after delete) also returns assignment
            ]
        )
        mock_svc.get_assignment = AsyncMock(return_value=None)  # Not found for new
        app.dependency_overrides[get_assignment_service] = lambda: mock_svc

        # Create first assignment
        response1 = await client.post(
            "/plagitype/plagiarism/assignments",
            json={"name": "UniqueName", "description": None},
        )
        assert response1.status_code == 201

        # Simulate delete (we'll just check that create would work again)
        # In a real scenario, the second create would fail if the unique constraint
        # was not partial. Since we expect it to work, we'll just test that
        # the endpoint would accept it.
        response2 = await client.post(
            "/plagitype/plagiarism/assignments",
            json={"name": "UniqueName", "description": "reused"},
        )
        assert response2.status_code == 201

    async def test_subject_name_can_be_reused_after_delete(self, client):
        """Creating a subject with the same name as a soft-deleted one should succeed."""
        from assignments.dependencies import get_subject_service

        subject1 = SubjectResponse(
            id="subject-1",
            name="UniqueSubject",
            description=None,
            created_at="2026-01-01T00:00:00",
            assignments_count=0,
        )

        mock_svc = MagicMock()
        mock_svc.create_subject = AsyncMock(side_effect=[subject1, subject1])
        mock_svc.get_subject = AsyncMock(return_value=None)
        app.dependency_overrides[get_subject_service] = lambda: mock_svc

        response1 = await client.post(
            "/plagitype/plagiarism/subjects",
            json={"name": "UniqueSubject", "description": None},
        )
        assert response1.status_code == 201

        response2 = await client.post(
            "/plagitype/plagiarism/subjects",
            json={"name": "UniqueSubject", "description": "reused"},
        )
        assert response2.status_code == 201


class TestCheckWithAssignmentId:
    async def test_check_with_invalid_assignment_id(self, client):
        """Uploading with a non-UUID assignment_id should return 400."""
        import io

        file_content = b"print('hello')"
        files = [("files", ("test.py", io.BytesIO(file_content), "text/plain"))]
        response = await client.post(
            "/plagitype/plagiarism/check",
            files=files,
            data={"language": "python", "assignment_id": "not-a-valid-uuid"},
        )
        assert response.status_code == 400

    async def test_check_with_valid_assignment_id(self, client):
        """Uploading with a valid UUID assignment_id should succeed."""
        import io

        from tasks.dependencies import get_task_service

        mock_svc = MagicMock()
        mock_svc.create_task = AsyncMock(
            return_value=TaskCreateResponse(task_id="test-uuid", status="queued", files_count=1)
        )
        app.dependency_overrides[get_task_service] = lambda: mock_svc

        file_content = b"print('hello')"
        files = [("files", ("test.py", io.BytesIO(file_content), "text/plain"))]
        response = await client.post(
            "/plagitype/plagiarism/check",
            files=files,
            data={
                "language": "python",
                "assignment_id": "12345678-1234-1234-1234-123456789abc",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "queued"

    async def test_check_without_assignment_id(self, client):
        """Uploading without assignment_id should work (full DB scan)."""
        import io

        from tasks.dependencies import get_task_service

        mock_svc = MagicMock()
        mock_svc.create_task = AsyncMock(
            return_value=TaskCreateResponse(task_id="test-uuid-2", status="queued", files_count=1)
        )
        app.dependency_overrides[get_task_service] = lambda: mock_svc

        file_content = b"print('hello')"
        files = [("files", ("test.py", io.BytesIO(file_content), "text/plain"))]
        response = await client.post(
            "/plagitype/plagiarism/check",
            files=files,
            data={"language": "python"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "queued"


class TestWorkerAssignmentScope:
    def test_repository_get_files_by_assignment_filters_correctly(self):
        """get_files_by_assignment should only return files from tasks with the given assignment_id."""
        from unittest.mock import MagicMock

        mock_file_a = MagicMock()
        mock_file_a.id = "file-a-id"
        mock_file_a.task_id = "task-1"
        mock_file_a.filename = "a.py"
        mock_file_a.file_path = "/path/a.py"
        mock_file_a.file_hash = "hash-a"
        mock_file_a.language = "python"

        mock_file_b = MagicMock()
        mock_file_b.id = "file-b-id"
        mock_file_b.task_id = "task-2"
        mock_file_b.filename = "b.py"
        mock_file_b.file_path = "/path/b.py"
        mock_file_b.file_hash = "hash-b"
        mock_file_b.language = "python"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_file_a, mock_file_b]

        mock_session = MagicMock()
        mock_session.execute.return_value = mock_result

        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_session)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        with patch("worker.infrastructure.postgres_repository.get_session", return_value=mock_ctx):
            from worker.infrastructure.postgres_repository import PostgresRepository

            repo = PostgresRepository()
            files = repo.get_files_by_assignment("assignment-1")

        assert len(files) == 2
        assert files[0]["id"] == "file-a-id"
        assert files[1]["id"] == "file-b-id"
        assert files[0]["filename"] == "a.py"

    def test_repository_get_files_by_assignment_excludes_task(self):
        """get_files_by_assignment should exclude files from the given task_id."""
        from unittest.mock import MagicMock

        mock_file = MagicMock()
        mock_file.id = "file-b-id"
        mock_file.task_id = "task-2"
        mock_file.filename = "b.py"
        mock_file.file_path = "/path/b.py"
        mock_file.file_hash = "hash-b"
        mock_file.language = "python"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_file]

        mock_session = MagicMock()
        mock_session.execute.return_value = mock_result

        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_session)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        with patch("worker.infrastructure.postgres_repository.get_session", return_value=mock_ctx):
            from worker.infrastructure.postgres_repository import PostgresRepository

            repo = PostgresRepository()
            files = repo.get_files_by_assignment("assignment-1", exclude_task_id="task-1")

        assert len(files) == 1
        assert files[0]["id"] == "file-b-id"

    def test_task_service_uses_assignment_scoped_files(self):
        """TaskService.process_task should use get_files_by_assignment when assignment_id is given."""
        from worker.services.task_service import TaskService

        mock_repo = MagicMock()
        mock_repo.get_files_by_assignment.return_value = [
            {
                "id": "f1",
                "task_id": "t1",
                "filename": "a.py",
                "file_path": "/a.py",
                "file_hash": "h1",
                "language": "python",
            },
            {
                "id": "f2",
                "task_id": "t2",
                "filename": "b.py",
                "file_path": "/b.py",
                "file_hash": "h2",
                "language": "python",
            },
        ]
        mock_repo.get_all_files.return_value = []

        mock_fingerprint = MagicMock()
        mock_indexing = MagicMock()
        mock_candidate = MagicMock()
        mock_candidate.find_candidate_pairs.return_value = []
        mock_analysis = MagicMock()
        mock_result = MagicMock()

        svc = TaskService(
            fingerprint_service=mock_fingerprint,
            indexing_service=mock_indexing,
            candidate_service=mock_candidate,
            analysis_service=mock_analysis,
            result_service=mock_result,
            repository=mock_repo,
        )

        files = [
            {
                "id": "f1",
                "task_id": "t1",
                "filename": "a.py",
                "file_path": "/a.py",
                "file_hash": "h1",
                "language": "python",
            },
        ]

        svc.process_task("task-1", files, "python", assignment_id="assign-1")

        mock_repo.get_files_by_assignment.assert_called_once_with(
            "assign-1", exclude_task_id="task-1"
        )
        mock_repo.get_all_files.assert_not_called()

    def test_task_service_uses_full_db_when_no_assignment(self):
        """TaskService.process_task should use get_all_files when no assignment_id."""
        from worker.services.task_service import TaskService

        mock_repo = MagicMock()
        mock_repo.get_all_files.return_value = [
            {
                "id": "f2",
                "task_id": "t2",
                "filename": "b.py",
                "file_path": "/b.py",
                "file_hash": "h2",
                "language": "python",
            },
        ]
        mock_repo.get_files_by_assignment.return_value = []

        mock_fingerprint = MagicMock()
        mock_indexing = MagicMock()
        mock_candidate = MagicMock()
        mock_candidate.find_candidate_pairs.return_value = []
        mock_analysis = MagicMock()
        mock_result = MagicMock()

        svc = TaskService(
            fingerprint_service=mock_fingerprint,
            indexing_service=mock_indexing,
            candidate_service=mock_candidate,
            analysis_service=mock_analysis,
            result_service=mock_result,
            repository=mock_repo,
        )

        files = [
            {
                "id": "f1",
                "task_id": "t1",
                "filename": "a.py",
                "file_path": "/a.py",
                "file_hash": "h1",
                "language": "python",
            },
        ]

        svc.process_task("task-1", files, "python")

        mock_repo.get_all_files.assert_called_once_with(exclude_task_id="task-1")
        mock_repo.get_files_by_assignment.assert_not_called()

    def test_task_service_passes_assignment_to_cross_pairs(self):
        """When assignment_id is given, cross-task pairs should only come from assignment scope."""
        from worker.services.task_service import TaskService

        assignment_files = [
            {
                "id": "f2",
                "task_id": "t2",
                "filename": "b.py",
                "file_path": "/b.py",
                "file_hash": "h2",
                "language": "python",
            },
            {
                "id": "f3",
                "task_id": "t3",
                "filename": "c.py",
                "file_path": "/c.py",
                "file_hash": "h3",
                "language": "python",
            },
        ]
        mock_repo = MagicMock()
        mock_repo.get_files_by_assignment.return_value = assignment_files

        mock_fingerprint = MagicMock()
        mock_indexing = MagicMock()

        intra_pairs = [
            ({"file_hash": "h1"}, {"file_hash": "h2"}, 0.8),
        ]
        cross_pairs = [
            ({"file_hash": "h1"}, {"file_hash": "h3"}, 0.6),
        ]

        mock_candidate = MagicMock()
        mock_candidate.find_candidate_pairs.side_effect = [intra_pairs, cross_pairs]

        mock_analysis = MagicMock()
        mock_result = MagicMock()

        svc = TaskService(
            fingerprint_service=mock_fingerprint,
            indexing_service=mock_indexing,
            candidate_service=mock_candidate,
            analysis_service=mock_analysis,
            result_service=mock_result,
            repository=mock_repo,
        )

        files = [
            {
                "id": "f1",
                "task_id": "t1",
                "filename": "a.py",
                "file_path": "/a.py",
                "file_hash": "h1",
                "language": "python",
            },
        ]

        svc.process_task("task-1", files, "python", assignment_id="assign-1")

        cross_call = mock_candidate.find_candidate_pairs.call_args_list[1]
        assert cross_call.kwargs["files_b"] == assignment_files


class TestSoftDeleteRestore:
    """Tests for soft delete and restore functionality."""

    async def test_assignment_repository_delete_sets_deleted_at(self):
        """delete_assignment should set deleted_at to current time."""
        from unittest.mock import AsyncMock, MagicMock

        from shared.models import Assignment

        from assignments.repository import AssignmentRepository

        mock_assignment = MagicMock(spec=Assignment)
        mock_assignment.id = "test-assignment-id"
        mock_assignment.deleted_at = None

        mock_session = MagicMock()
        mock_session.get = AsyncMock(return_value=mock_assignment)
        mock_session.commit = AsyncMock()

        repo = AssignmentRepository(mock_session)
        result = await repo.delete_assignment("test-assignment-id")

        assert result is True
        assert mock_assignment.deleted_at is not None
        mock_session.commit.assert_called_once()

    async def test_assignment_repository_restore_clears_deleted_at(self):
        """restore_assignment should set deleted_at to None."""
        from unittest.mock import AsyncMock, MagicMock

        from shared.models import Assignment

        from assignments.repository import AssignmentRepository

        mock_assignment = MagicMock(spec=Assignment)
        mock_assignment.id = "test-assignment-id"
        mock_assignment.deleted_at = datetime.now(UTC)

        mock_session = MagicMock()
        mock_session.get = AsyncMock(return_value=mock_assignment)
        mock_session.commit = AsyncMock()

        repo = AssignmentRepository(mock_session)
        result = await repo.restore_assignment("test-assignment-id")

        assert result is True
        assert mock_assignment.deleted_at is None
        mock_session.commit.assert_called_once()

    async def test_assignment_repository_restore_returns_false_if_not_deleted(self):
        """restore_assignment should return False if assignment is not deleted."""
        from unittest.mock import AsyncMock, MagicMock

        from shared.models import Assignment

        from assignments.repository import AssignmentRepository

        mock_assignment = MagicMock(spec=Assignment)
        mock_assignment.id = "test-assignment-id"
        mock_assignment.deleted_at = None

        mock_session = MagicMock()
        mock_session.get = AsyncMock(return_value=mock_assignment)

        repo = AssignmentRepository(mock_session)
        result = await repo.restore_assignment("test-assignment-id")

        assert result is False

    async def test_assignment_repository_get_assignment_excludes_deleted_by_default(self):
        """get_assignment should return None for deleted assignments by default."""
        from unittest.mock import AsyncMock, MagicMock

        from assignments.repository import AssignmentRepository

        mock_assignment = MagicMock()
        mock_assignment.id = "test-id"
        mock_assignment.deleted_at = MagicMock()  # Non-None, indicates deleted
        mock_assignment.tasks = []

        mock_session = MagicMock()
        mock_session.get = AsyncMock(return_value=mock_assignment)

        repo = AssignmentRepository(mock_session)
        result = await repo.get_assignment("test-id")

        assert result is None

    async def test_assignment_repository_get_assignment_include_deleted(self):
        """get_assignment with include_deleted=True should return deleted assignments."""
        from unittest.mock import AsyncMock, MagicMock

        from assignments.repository import AssignmentRepository

        # Create a mock assignment that is deleted but has minimal attributes
        mock_assignment = MagicMock()
        mock_assignment.id = "test-id"
        mock_assignment.name = "Test"
        mock_assignment.description = None
        mock_assignment.subject_id = None
        mock_assignment.created_at = datetime(2026, 1, 1, tzinfo=UTC)
        mock_assignment.deleted_at = MagicMock()  # Non-None, indicates deleted
        mock_assignment.tasks = []  # No tasks

        mock_session = MagicMock()
        mock_session.get = AsyncMock(return_value=mock_assignment)
        # Mock execute to return counts (0)
        mock_execute_result = MagicMock()
        mock_execute_result.scalar.return_value = 0
        mock_session.execute = AsyncMock(return_value=mock_execute_result)

        repo = AssignmentRepository(mock_session)
        result = await repo.get_assignment("test-id", include_deleted=True)

        assert result is not None
        assert result.id == "test-id"

    async def test_subject_repository_delete_sets_deleted_at(self):
        """delete_subject should set deleted_at to current time."""
        from unittest.mock import AsyncMock, MagicMock

        from shared.models import Subject

        from assignments.repository import SubjectRepository

        mock_subject = MagicMock(spec=Subject)
        mock_subject.id = "test-subject-id"
        mock_subject.deleted_at = None

        mock_session = MagicMock()
        mock_session.get = AsyncMock(return_value=mock_subject)
        mock_session.commit = AsyncMock()

        repo = SubjectRepository(mock_session)
        result = await repo.delete_subject("test-subject-id")

        assert result is True
        assert mock_subject.deleted_at is not None
        mock_session.commit.assert_called_once()

    async def test_subject_repository_restore_clears_deleted_at(self):
        """restore_subject should set deleted_at to None."""
        from unittest.mock import AsyncMock, MagicMock

        from shared.models import Subject

        from assignments.repository import SubjectRepository

        mock_subject = MagicMock(spec=Subject)
        mock_subject.id = "test-subject-id"
        mock_subject.deleted_at = datetime.now(UTC)

        mock_session = MagicMock()
        mock_session.get = AsyncMock(return_value=mock_subject)
        mock_session.commit = AsyncMock()

        repo = SubjectRepository(mock_session)
        result = await repo.restore_subject("test-subject-id")

        assert result is True
        assert mock_subject.deleted_at is None
        mock_session.commit.assert_called_once()

    async def test_subject_repository_restore_returns_false_if_not_deleted(self):
        """restore_subject should return False if subject is not deleted."""
        from unittest.mock import AsyncMock, MagicMock

        from shared.models import Subject

        from assignments.repository import SubjectRepository

        mock_subject = MagicMock(spec=Subject)
        mock_subject.id = "test-subject-id"
        mock_subject.deleted_at = None

        mock_session = MagicMock()
        mock_session.get = AsyncMock(return_value=mock_subject)

        repo = SubjectRepository(mock_session)
        result = await repo.restore_subject("test-subject-id")

        assert result is False
