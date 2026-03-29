"""
Tests for assignment-scoped analysis feature.

Tests cover:
- Assignment CRUD endpoints
- Upload with assignment_id parameter
- Worker assignment-scoped file filtering
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Resolve src path relative to project root (parent of tests/)
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_project_root, "src"))

from app import app  # noqa: E402
from assignments.schemas import AssignmentResponse  # noqa: E402
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
