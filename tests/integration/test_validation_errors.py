"""
Validation Error Tests - Test API validation and error handling.

These tests verify that the API properly validates input and returns appropriate
error responses (422 for validation errors, 404 for not found, etc.)
"""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


class TestAssignmentValidation:
    """Test assignment input validation."""

    async def test_create_assignment_empty_body(self, client: AsyncClient):
        """Test creating assignment with empty body returns 422."""
        response = await client.post("/plagitype/plagiarism/assignments", json={})
        assert response.status_code == 422, f"Expected 422: {response.text}"

    async def test_create_assignment_missing_name(self, client: AsyncClient):
        """Test creating assignment without name returns 422."""
        response = await client.post(
            "/plagitype/plagiarism/assignments",
            json={"description": "Test"},
        )
        assert response.status_code == 422, f"Expected 422: {response.text}"

    async def test_update_assignment_invalid_id(self, client: AsyncClient):
        """Test updating with invalid UUID format returns 422."""
        response = await client.patch(
            "/plagitype/plagiarism/assignments/not-a-uuid",
            json={"name": "New Name"},
        )
        assert response.status_code == 422, f"Expected 422: {response.text}"


class TestTaskValidation:
    """Test task input validation."""

    async def test_create_task_empty_body(self, client: AsyncClient):
        """Test creating task with empty body returns 422."""
        response = await client.post("/plagitype/plagiarism/check", data={}, files=[])
        assert response.status_code == 422, f"Expected 422: {response.text}"

    async def test_create_task_invalid_language(self, client: AsyncClient):
        """Test creating task with invalid language returns 422."""
        response = await client.post(
            "/plagitype/plagiarism/check", data={"language": "not-a-language"}, files=[]
        )
        assert response.status_code == 422, f"Expected 422: {response.text}"

    async def test_get_task_invalid_uuid(self, client: AsyncClient):
        """Test getting task with invalid UUID returns 422."""
        response = await client.get("/plagitype/plagiarism/tasks/invalid-uuid-123")
        assert response.status_code == 422, f"Expected 422: {response.text}"


class TestSubjectValidation:
    """Test subject input validation."""

    async def test_create_subject_empty_body(self, client: AsyncClient):
        """Test creating subject with empty body returns 422."""
        response = await client.post("/plagitype/plagiarism/subjects", json={})
        assert response.status_code == 422, f"Expected 422: {response.text}"

    async def test_create_subject_missing_name(self, client: AsyncClient):
        """Test creating subject without name returns 422."""
        response = await client.post(
            "/plagitype/plagiarism/subjects",
            json={"description": "Test"},
        )
        assert response.status_code == 422, f"Expected 422: {response.text}"


class TestPaginationValidation:
    """Test pagination parameter validation."""

    async def test_negative_offset_returns_error(self, client: AsyncClient):
        """Test negative offset returns 422."""
        response = await client.get("/plagitype/plagiarism/assignments?offset=-1")
        assert response.status_code == 422, f"Expected 422: {response.text}"

    async def test_negative_limit_returns_error(self, client: AsyncClient):
        """Test negative limit returns 422."""
        response = await client.get("/plagitype/plagiarism/assignments?limit=-5")
        assert response.status_code == 422, f"Expected 422: {response.text}"

    async def test_non_numeric_limit_returns_error(self, client: AsyncClient):
        """Test non-numeric limit returns 422."""
        response = await client.get("/plagitype/plagiarism/assignments?limit=abc")
        assert response.status_code == 422, f"Expected 422: {response.text}"


class Test404NotFound:
    """Test 404 responses for non-existent resources."""

    async def test_get_nonexistent_assignment(self, client: AsyncClient):
        """Test getting non-existent assignment returns 404."""
        fake_uuid = "00000000-0000-0000-0000-000000000001"
        response = await client.get(f"/plagitype/plagiarism/assignments/{fake_uuid}")
        assert response.status_code == 404, f"Expected 404: {response.text}"

    async def test_get_nonexistent_task(self, client: AsyncClient):
        """Test getting non-existent task returns 404."""
        fake_uuid = "00000000-0000-0000-0000-000000000002"
        response = await client.get(f"/plagitype/plagiarism/tasks/{fake_uuid}")
        assert response.status_code == 404, f"Expected 404: {response.text}"

    async def test_get_nonexistent_subject(self, client: AsyncClient):
        """Test getting non-existent subject returns 404."""
        fake_uuid = "00000000-0000-0000-0000-000000000003"
        response = await client.get(f"/plagitype/plagiarism/subjects/{fake_uuid}")
        assert response.status_code == 404, f"Expected 404: {response.text}"


class TestMethodNotAllowed:
    """Test correct handling of unsupported methods."""

    async def test_delete_on_get_endpoint_returns_405(self, client: AsyncClient):
        """Test DELETE on GET-only endpoint returns 405."""
        response = await client.delete("/plagitype/plagiarism/assignments")
        assert response.status_code == 405, f"Expected 405: {response.text}"

    async def test_put_on_create_endpoint_returns_405(self, client: AsyncClient):
        """Test PUT on POST-only endpoint returns 405."""
        response = await client.put(
            "/plagitype/plagiarism/assignments",
            json={"name": "Test"},
        )
        assert response.status_code == 405, f"Expected 405: {response.text}"
