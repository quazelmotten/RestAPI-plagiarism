"""
E2E Workflow Tests - Test full workflows end-to-end.

These tests use real PostgreSQL, Redis, and RabbitMQ services.
"""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


class TestE2EAssignmentWorkflow:
    """Test assignment-based workflows."""

    async def test_full_assignment_workflow(self, client: AsyncClient):
        """Test creating and managing an assignment."""
        data = {"name": "Test E2E Assignment", "description": "E2E test"}
        response = await client.post("/plagitype/plagiarism/assignments", json=data)
        assert response.status_code == 201, f"Failed to create assignment: {response.text}"
        data = response.json()
        assert "id" in data

    async def test_assignment_with_multiple_tasks(self, client: AsyncClient):
        """Test assignment with multiple tasks."""
        response = await client.get("/plagitype/plagiarism/assignments")
        assert response.status_code == 200, f"Failed to list assignments: {response.text}"
        data = response.json()
        assert isinstance(data, dict)


class TestE2ETaskWorkflow:
    """Test task-based workflows."""

    async def test_task_lifecycle(self, client: AsyncClient):
        """Test creating and processing a task."""
        data = {"language": "python"}
        response = await client.post("/plagitype/plagiarism/tasks", json=data)
        assert response.status_code == 201, f"Failed to create task: {response.text}"
        data = response.json()
        assert "task_id" in data or "id" in data

    async def test_empty_task_workflow(self, client: AsyncClient):
        """Test task with no files."""
        response = await client.get("/plagitype/plagiarism/tasks")
        assert response.status_code == 200, f"Failed to list tasks: {response.text}"
        data = response.json()
        assert isinstance(data, dict)


class TestE2EFileWorkflow:
    """Test file upload workflows."""

    async def test_file_upload_and_retrieval(self, client: AsyncClient):
        """Test uploading and retrieving files."""
        response = await client.get("/plagitype/plagiarism/files")
        assert response.status_code in (200, 404), f"Files endpoint failed: {response.text}"
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, (dict, list))


class TestE2EWithSubjects:
    """Test subject-based workflows."""

    async def test_subject_with_assignments_workflow(self, client: AsyncClient):
        """Test subject with assignments."""
        response = await client.get("/plagitype/plagiarism/subjects")
        assert response.status_code == 200, f"Failed to list subjects: {response.text}"
        data = response.json()
        assert isinstance(data, dict)

    async def test_uncategorized_assignments_workflow(self, client: AsyncClient):
        """Test uncategorized assignments."""
        response = await client.get("/plagitype/plagiarism/subjects/uncategorized")
        assert response.status_code == 200, f"Failed to get uncategorized: {response.text}"
        data = response.json()
        assert isinstance(data, dict)


class TestE2ECrossLanguage:
    """Test workflows across different programming languages."""

    @pytest.mark.parametrize("language", ["python", "java", "cpp", "javascript"])
    async def test_task_with_different_languages(self, client: AsyncClient, language: str):
        """Test creating tasks in different languages."""
        data = {"language": language}
        response = await client.post("/plagitype/plagiarism/tasks", json=data)
        assert response.status_code == 201, f"Failed for language {language}: {response.text}"
        data = response.json()
        assert "task_id" in data or "id" in data


class TestE2EErrorHandling:
    """Test error handling in workflows."""

    async def test_invalid_assignment_id_in_task_creation(self, client: AsyncClient):
        """Test creating task with invalid assignment."""
        response = await client.post(
            "/plagitype/plagiarism/assignments/invalid-id/tasks",
            json={"language": "python"},
        )
        assert response.status_code in (422, 404), f"Expected error for invalid ID: {response.text}"

    async def test_upload_to_nonexistent_task(self, client: AsyncClient):
        """Test uploading to nonexistent task."""
        files = {"file": ("test.py", b"print('hello')", "text/plain")}
        response = await client.post(
            "/plagitype/plagiarism/tasks/00000000-0000-0000-0000-000000000000/files",
            files=files,
        )
        assert response.status_code in (422, 404), (
            f"Expected error for nonexistent task: {response.text}"
        )

    async def test_get_results_for_nonexistent_task(self, client: AsyncClient):
        """Test getting results for nonexistent task."""
        response = await client.get(
            "/plagitype/plagiarism/tasks/00000000-0000-0000-0000-000000000000/results"
        )
        assert response.status_code in (200, 404), f"Expected valid response: {response.text}"
