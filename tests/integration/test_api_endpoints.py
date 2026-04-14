"""
API Integration Tests - Test all major endpoints with real services.

These tests use real PostgreSQL, Redis, and RabbitMQ services via docker-compose.test.yml.
Each test is isolated and auto-seeds its own data.
"""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


class TestHealthEndpoints:
    """Test health and version endpoints."""

    async def test_health_check(self, client: AsyncClient):
        """Test health endpoint returns correct status."""
        response = await client.get("/health")
        assert response.status_code == 200, f"Health check failed: {response.text}"
        data = response.json()
        assert "status" in data
        assert "checks" in data

    async def test_version_endpoint(self, client: AsyncClient):
        """Test version endpoint returns API version."""
        response = await client.get("/version")
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert "service" in data


class TestAssignmentEndpoints:
    """Test assignment CRUD endpoints."""

    async def test_create_assignment(self, client: AsyncClient, sample_assignment_data: dict):
        """Test creating a new assignment."""
        response = await client.post(
            "/plagitype/plagiarism/assignments",
            json=sample_assignment_data,
        )
        assert response.status_code == 201, f"Failed to create assignment: {response.text}"
        data = response.json()
        assert "id" in data
        assert isinstance(data, dict)

    async def test_list_assignments(self, client: AsyncClient):
        """Test listing assignments with pagination."""
        response = await client.get("/plagitype/plagiarism/assignments")
        assert response.status_code == 200, f"List assignments failed: {response.text}"
        data = response.json()
        assert isinstance(data, dict)
        assert "items" in data or "total" in data

    async def test_get_assignment_not_found(self, client: AsyncClient):
        """Test getting non-existent assignment returns 404."""
        response = await client.get(
            "/plagitype/plagiarism/assignments/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 404

    async def test_update_assignment(self, client: AsyncClient, sample_assignment_data: dict):
        """Test updating an assignment."""
        create_response = await client.post(
            "/plagitype/plagiarism/assignments",
            json=sample_assignment_data,
        )
        if create_response.status_code != 201:
            pytest.skip(f"Could not create assignment: {create_response.status_code}")

        assignment = create_response.json()
        assignment_id = assignment.get("id")
        if not assignment_id:
            pytest.skip("No assignment ID")

        update_data = {"name": "Updated Assignment Name"}
        response = await client.patch(
            f"/plagitype/plagiarism/assignments/{assignment_id}",
            json=update_data,
        )
        assert response.status_code == 200, f"Failed to update assignment: {response.text}"
        data = response.json()
        assert data.get("name") == "Updated Assignment Name"

    async def test_delete_assignment(self, client: AsyncClient, sample_assignment_data: dict):
        """Test deleting an assignment."""
        create_response = await client.post(
            "/plagitype/plagiarism/assignments",
            json=sample_assignment_data,
        )
        if create_response.status_code != 201:
            pytest.skip(f"Could not create assignment: {create_response.status_code}")

        assignment = create_response.json()
        assignment_id = assignment.get("id")
        if not assignment_id:
            pytest.skip("No assignment ID")

        response = await client.delete(f"/plagitype/plagiarism/assignments/{assignment_id}")
        assert response.status_code == 204, f"Failed to delete assignment: {response.text}"


class TestTaskEndpoints:
    """Test task management endpoints."""

    async def test_create_task(self, client: AsyncClient, sample_file_content: bytes):
        """Test creating a new plagiarism check task."""
        files = {"files": ("test.py", sample_file_content, "text/plain")}
        data = {"language": "python"}
        response = await client.post(
            "/plagitype/plagiarism/check",
            files=files,
            data=data,
        )
        assert response.status_code == 201, f"Failed to create task: {response.text}"
        data = response.json()
        assert "task_id" in data or "id" in data

    async def test_get_task_not_found(self, client: AsyncClient):
        """Test getting non-existent task returns 404."""
        response = await client.get(
            "/plagitype/plagiarism/tasks/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 404

    async def test_get_task_invalid_uuid(self, client: AsyncClient):
        """Test getting task with invalid UUID returns 422."""
        response = await client.get("/plagitype/plagiarism/tasks/not-a-uuid")
        assert response.status_code == 422


class TestSubjectEndpoints:
    """Test subject management endpoints."""

    async def test_create_subject(self, client: AsyncClient):
        """Test creating a subject."""
        subject_data = {
            "name": "Test Subject",
            "description": "Test subject for integration tests",
        }
        response = await client.post(
            "/plagitype/plagiarism/subjects",
            json=subject_data,
        )
        assert response.status_code == 201, f"Failed to create subject: {response.text}"
        data = response.json()
        assert "id" in data

    async def test_list_subjects(self, client: AsyncClient):
        """Test listing subjects."""
        response = await client.get("/plagitype/plagiarism/subjects")
        assert response.status_code == 200, f"List subjects failed: {response.text}"
        data = response.json()
        assert isinstance(data, dict)

    async def test_get_uncategorized_assignments(self, client: AsyncClient):
        """Test getting uncategorized assignments."""
        response = await client.get("/plagitype/plagiarism/assignments/uncategorized")
        assert response.status_code == 200, f"Failed to get uncategorized: {response.text}"
        data = response.json()
        assert isinstance(data, list)


class TestEdgeCases:
    """Test edge cases and error handling."""

    async def test_invalid_assignment_id_format(self, client: AsyncClient):
        """Test invalid UUID format for assignment."""
        response = await client.get("/plagitype/plagiarism/assignments/invalid-uuid")
        assert response.status_code == 422

    async def test_invalid_task_id_format(self, client: AsyncClient):
        """Test invalid UUID format for task."""
        response = await client.get("/plagitype/plagiarism/tasks/invalid-uuid")
        assert response.status_code == 422

    async def test_pagination_parameters(self, client: AsyncClient):
        """Test pagination with custom limit and offset."""
        response = await client.get("/plagitype/plagiarism/assignments?limit=5&offset=0")
        assert response.status_code == 200, f"Pagination failed: {response.text}"
        data = response.json()
        assert isinstance(data, dict)

    async def test_invalid_pagination_limit(self, client: AsyncClient):
        """Test invalid pagination limit returns 422."""
        response = await client.get("/plagitype/plagiarism/assignments?limit=1000")
        assert response.status_code == 422, f"Expected 422 for invalid limit: {response.text}"
