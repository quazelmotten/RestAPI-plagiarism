"""
Integration tests for API key endpoints using TestClient.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from app import app

from auth.models import ApiKey, User
from auth.service import create_access_token, get_password_hash

client = TestClient(app, base_url="http://testserver/plagitype")


class TestApiKeyEndpoints:
    """Integration tests for API key endpoints."""

    @pytest.fixture
    def mock_user(self):
        """Fixture for a test user."""
        user = User(
            id="test-user-123",
            email="test@example.com",
            hashed_password=get_password_hash("Password123!"),
            is_global_admin=False,
            session_version=1,
            created_at=datetime.now(UTC),
            last_login=None,
        )
        return user

    @pytest.fixture
    def mock_admin_user(self):
        """Fixture for an admin test user."""
        user = User(
            id="admin-user-456",
            email="admin@example.com",
            hashed_password=get_password_hash("AdminPass123!"),
            is_global_admin=True,
            session_version=1,
            created_at=datetime.now(UTC),
            last_login=datetime.now(UTC),
        )
        return user

    @pytest.fixture
    def auth_headers(self, mock_user):
        """Fixture for authentication headers with valid JWT token."""
        token = create_access_token(
            {
                "sub": str(mock_user.id),
                "email": mock_user.email,
                "is_global_admin": mock_user.is_global_admin,
                "sv": mock_user.session_version,
            }
        )
        return {"Authorization": f"Bearer {token}"}

    @pytest.fixture
    def setup_mocks(self, monkeypatch, mock_user, mock_admin_user):
        """Setup test mocks for authenticated requests."""
        from unittest.mock import MagicMock

        # Mock async_session_maker
        mock_session = AsyncMock()

        async def mock_execute(query):
            mock_result = MagicMock()
            query_str = str(query).lower()

            # Handle User queries
            if "users" in query_str:
                if "test@example.com" in query_str:
                    mock_result.scalar_one_or_none.return_value = mock_user
                elif "admin@example.com" in query_str:
                    mock_result.scalar_one_or_none.return_value = mock_admin_user
                elif "test-user-123" in query_str:
                    mock_result.scalar_one_or_none.return_value = mock_user
                elif "admin-user-456" in query_str:
                    mock_result.scalar_one_or_none.return_value = mock_admin_user
                else:
                    mock_result.scalars.return_value.all.return_value = [mock_user, mock_admin_user]
            # Handle ApiKey queries
            elif "api_keys" in query_str:
                # For listing keys
                if "order_by" in query_str or "select" in query_str:
                    mock_api_key = MagicMock(spec=ApiKey)
                    mock_api_key.id = "test-key-id"
                    mock_api_key.name = "Test Key"
                    mock_api_key.created_at = datetime.now(UTC)
                    mock_api_key.last_used_at = None
                    mock_api_key.expires_at = None
                    mock_api_key.user_id = mock_user.id
                    mock_result.scalars.return_value.all.return_value = [mock_api_key]
                    mock_result.scalar_one_or_none.return_value = None
                # For getting a specific key by ID
                elif "where" in query_str:
                    # Return first key found (simplified)
                    mock_result.scalar_one_or_none.return_value = None
                else:
                    mock_result.scalar_one_or_none.return_value = None
            else:
                mock_result.scalar_one_or_none.return_value = None

            return mock_result

        mock_session.execute = mock_execute
        mock_session.add.return_value = None
        mock_session.commit.return_value = None
        mock_session.flush.return_value = None

        mock_session_maker = MagicMock()
        mock_session_maker.return_value.__aenter__.return_value = mock_session

        monkeypatch.setattr("auth.service.async_session_maker", mock_session_maker)

        # Mock blacklist service
        mock_blacklist = AsyncMock()
        mock_blacklist.is_token_blacklisted.return_value = False
        mock_blacklist.blacklist_token.return_value = None
        monkeypatch.setattr("auth.blacklist_service.blacklist_service", mock_blacklist)

        # FastAPI dependency overrides for authenticated user
        from auth.dependencies import get_current_user, require_global_admin

        original_overrides = app.dependency_overrides.copy()

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[require_global_admin] = lambda: mock_admin_user

        yield

        app.dependency_overrides = original_overrides

    def test_create_api_key_endpoint(self, auth_headers, setup_mocks):
        """Test POST /api-keys creates a new API key."""
        with patch("auth.service.AuthService.create_api_key") as mock_create:
            mock_key = MagicMock()
            mock_key.id = "test-key-id"
            mock_key.name = "My Test Key"
            mock_key.created_at = datetime.now(UTC)
            mock_key.last_used_at = None
            mock_key.expires_at = None
            mock_create.return_value = (mock_key, "raw_test_key_12345")

            response = client.post(
                "/auth/api-keys",
                json={"name": "My Test Key", "expires_in_days": None},
                headers=auth_headers,
            )

        assert response.status_code == 201
        json_data = response.json()
        assert "raw_key" in json_data
        assert json_data["name"] == "My Test Key"

    def test_list_api_keys_endpoint(self, auth_headers, setup_mocks):
        """Test GET /api-keys returns list of keys."""
        with patch("auth.service.AuthService.list_api_keys") as mock_list:
            mock_key = MagicMock()
            mock_key.id = "key-1"
            mock_key.name = "Test Key"
            mock_key.created_at = datetime.now(UTC)
            mock_key.last_used_at = None
            mock_key.expires_at = None
            mock_list.return_value = [mock_key]

            response = client.get("/auth/api-keys", headers=auth_headers)

        assert response.status_code == 200
        json_data = response.json()
        assert isinstance(json_data, list)

    def test_revoke_api_key_endpoint(self, auth_headers, setup_mocks):
        """Test DELETE /api-keys/{key_id} revokes a key."""
        with patch("auth.service.AuthService.revoke_api_key") as mock_revoke:
            mock_revoke.return_value = True

            response = client.delete("/auth/api-keys/test-key-id", headers=auth_headers)

        assert response.status_code == 204

    def test_revoke_api_key_not_found(self, auth_headers, setup_mocks):
        """Test DELETE /api-keys/{key_id} with non-existent key returns 404."""
        with patch("auth.service.AuthService.revoke_api_key") as mock_revoke:
            mock_revoke.return_value = False

            response = client.delete("/auth/api-keys/non-existent-key", headers=auth_headers)

        assert response.status_code == 404

    def test_api_key_with_jwt_fallback(self, auth_headers, setup_mocks):
        """Test that JWT still works when X-API-Key header is not present."""
        response = client.get("/auth/me", headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["email"] == "test@example.com"

    def test_invalid_api_key_returns_401(self):
        """Test that an invalid API key returns 401."""
        # Mock the get_user_by_api_key to return None (invalid key)
        with patch("auth.service.AuthService.get_user_by_api_key") as mock_get_by_key:
            mock_get_by_key.return_value = None

            api_key_headers = {"X-API-Key": "invalid-api-key-12345"}
            response = client.get("/auth/me", headers=api_key_headers)
            assert response.status_code == 401
            assert "invalid api key" in response.json()["detail"].lower()

    def test_admin_list_all_api_keys(self, auth_headers, setup_mocks):
        """Test that admin can list all API keys."""
        with patch("auth.service.AuthService.list_all_api_keys") as mock_list_all:
            mock_key1 = MagicMock()
            mock_key1.id = "key-1"
            mock_key1.name = "User 1 Key"
            mock_key1.created_at = datetime.now(UTC)
            mock_key1.last_used_at = None
            mock_key1.expires_at = None
            mock_key1.user_id = "user-123"

            mock_key2 = MagicMock()
            mock_key2.id = "key-2"
            mock_key2.name = "User 2 Key"
            mock_key2.created_at = datetime.now(UTC)
            mock_key2.last_used_at = datetime.now(UTC)
            mock_key2.expires_at = None
            mock_key2.user_id = "user-456"

            mock_list_all.return_value = [mock_key1, mock_key2]

            response = client.get("/auth/api-keys/all", headers=auth_headers)

        assert response.status_code == 200
        json_data = response.json()
        assert isinstance(json_data, list)
        assert len(json_data) == 2
