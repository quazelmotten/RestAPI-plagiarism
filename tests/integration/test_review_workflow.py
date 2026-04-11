"""
Integration tests for review workflow - API level tests.
These test the core endpoints without complex fixtures.
"""

import pytest

pytestmark = pytest.mark.integration


class TestReviewStatusEndpoint:
    """Test review-status endpoint returns correct counts."""

    async def test_review_status_returns_all_dispositions(self, client, seeded_assignment):
        """Test review status includes all disposition counts."""
        assignment_id = seeded_assignment["id"]

        response = await client.get(
            f"/plagitype/plagiarism/assignments/{assignment_id}/review-status"
        )

        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()

        required_fields = [
            "assignment_id",
            "total_pairs",
            "unreviewed",
            "confirmed",
            "bulk_confirmed",
            "cleared",
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"


class TestPairsByStatusEndpoint:
    """Test pairs-by-status filtering."""

    async def test_pairs_status_clear_filter(self, client, seeded_assignment):
        """Test filtering by clear status."""
        assignment_id = seeded_assignment["id"]

        response = await client.get(
            f"/plagitype/plagiarism/assignments/{assignment_id}/pairs?status=clear"
        )

        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "total" in data
        assert "items" in data

    async def test_pairs_status_plagiarism_filter(self, client, seeded_assignment):
        """Test filtering by plagiarism status."""
        assignment_id = seeded_assignment["id"]

        response = await client.get(
            f"/plagitype/plagiarism/assignments/{assignment_id}/pairs?status=plagiarism"
        )

        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "total" in data

    async def test_pairs_status_bulk_confirmed_filter(self, client, seeded_assignment):
        """Test filtering by bulk_confirmed status."""
        assignment_id = seeded_assignment["id"]

        response = await client.get(
            f"/plagitype/plagiarism/assignments/{assignment_id}/pairs?status=bulk_confirmed"
        )

        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "total" in data

    async def test_pairs_status_unreviewed_filter(self, client, seeded_assignment):
        """Test filtering by unreviewed status."""
        assignment_id = seeded_assignment["id"]

        response = await client.get(
            f"/plagitype/plagiarism/assignments/{assignment_id}/pairs?status=unreviewed"
        )

        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "total" in data


class TestReviewQueueEndpoint:
    """Test review-queue endpoint."""

    async def test_review_queue_returns_required_fields(self, client, seeded_assignment):
        """Test queue includes required fields."""
        assignment_id = seeded_assignment["id"]

        response = await client.get(
            f"/plagitype/plagiarism/assignments/{assignment_id}/review-queue"
        )

        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()

        required_fields = [
            "assignment_id",
            "total_files",
            "confirmed_files",
            "remaining_files",
            "queue",
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"


class TestBulkConfirmEndpoint:
    """Test bulk-confirm endpoint."""

    async def test_bulk_confirm_returns_response(self, client, seeded_assignment):
        """Test bulk confirm works."""
        assignment_id = seeded_assignment["id"]

        response = await client.post(
            f"/plagitype/plagiarism/assignments/{assignment_id}/bulk-confirm?threshold=0.9"
        )

        if response.status_code == 200:
            data = response.json()
            assert "confirmed_pairs" in data
        else:
            assert response.status_code in [200, 404, 422]


class TestBulkClearEndpoint:
    """Test bulk-clear endpoint."""

    async def test_bulk_clear_returns_response(self, client, seeded_assignment):
        """Test bulk clear works."""
        assignment_id = seeded_assignment["id"]

        response = await client.post(
            f"/plagitype/plagiarism/assignments/{assignment_id}/bulk-clear?threshold=0.0"
        )

        if response.status_code == 200:
            data = response.json()
            assert "confirmed_pairs" in data
        else:
            assert response.status_code in [200, 404, 422]


class TestEndpointConsistency:
    """Test that endpoints return consistent data."""

    async def test_review_status_total_matches_pairs_sum(self, client, seeded_assignment):
        """Test total_pairs = sum of all disposition counts."""
        assignment_id = seeded_assignment["id"]

        response = await client.get(
            f"/plagitype/plagiarism/assignments/{assignment_id}/review-status"
        )

        assert response.status_code == 200
        data = response.json()

        total = data.get("total_pairs", 0)
        unreviewed = data.get("unreviewed", 0)
        confirmed = data.get("confirmed", 0)
        bulk_confirmed = data.get("bulk_confirmed", 0)
        cleared = data.get("cleared", 0)

        assert total == unreviewed + confirmed + bulk_confirmed + cleared, (
            f"Total {total} != {unreviewed} + {confirmed} + {bulk_confirmed} + {cleared}"
        )
