"""
Integration tests for authentication router endpoints using TestClient.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from src.app import app

from auth.models import User
from auth.service import create_access_token, get_password_hash

client = TestClient(app, base_url="http://testserver/plagitype")


class TestAuthRouterIntegration:
    """Integration tests for auth router endpoints."""

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
        """Fixture for authentication headers with valid token."""
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
    def admin_auth_headers(self, mock_admin_user):
        """Fixture for authentication headers with admin token."""
        token = create_access_token(
            {
                "sub": str(mock_admin_user.id),
                "email": mock_admin_user.email,
                "is_global_admin": mock_admin_user.is_global_admin,
                "sv": mock_admin_user.session_version,
            }
        )
        return {"Authorization": f"Bearer {token}"}

    @pytest.fixture(autouse=True)
    def setup_test_mocks(self, monkeypatch, mock_user, mock_admin_user):
        """Setup all test mocks including dependency overrides and external services."""
        from unittest.mock import MagicMock

        # Mock async_session_maker to return mock session with test users
        mock_session = AsyncMock()

        async def mock_execute(query):
            mock_result = MagicMock()
            query_str = str(query)

            if "test-user-123" in query_str or "admin-user-456" in query_str:
                if "admin-user-456" in query_str:
                    user = mock_admin_user
                else:
                    user = mock_user
                mock_result.scalar_one_or_none.return_value = user
            elif (
                "test@example.com" in query_str.lower() or "admin@example.com" in query_str.lower()
            ):
                if "admin@example.com" in query_str.lower():
                    user = mock_admin_user
                else:
                    user = mock_user
                mock_result.scalar_one_or_none.return_value = user
            else:
                mock_result.scalars.return_value.all.return_value = [mock_user, mock_admin_user]
                mock_result.scalar_one_or_none.return_value = None

            return mock_result

        mock_session.execute = mock_execute
        mock_session.add.return_value = None
        mock_session.commit.return_value = None
        mock_session.refresh.side_effect = lambda user: setattr(user, "id", user.id or "new-id")

        mock_session_maker = MagicMock()
        mock_session_maker.return_value.__aenter__.return_value = mock_session

        monkeypatch.setattr("auth.service.async_session_maker", mock_session_maker)

        # Mock blacklist service to avoid Redis
        mock_blacklist = AsyncMock()
        mock_blacklist.is_token_blacklisted.return_value = False
        mock_blacklist.blacklist_token.return_value = None
        monkeypatch.setattr("auth.blacklist_service.blacklist_service", mock_blacklist)

        # FastAPI dependency overrides - this is what actually fixes the 401 errors
        from src.app import app as test_app

        from auth.dependencies import get_current_user, require_global_admin

        test_app.dependency_overrides[get_current_user] = lambda: mock_user
        test_app.dependency_overrides[require_global_admin] = lambda: mock_admin_user

        yield

        # Clean up overrides after test
        test_app.dependency_overrides.clear()

    @patch("auth.service.AuthService.get_user_by_email")
    @patch("auth.service.AuthService.create_user")
    def test_register_new_user(self, mock_create_user, mock_get_user, mock_user):
        """Test registering a new user."""
        mock_get_user.return_value = None
        mock_create_user.return_value = mock_user

        response = client.post(
            "/auth/register", json={"email": "newuser@example.com", "password": "NewPass123!"}
        )

        assert response.status_code == 201
        assert response.json()["email"] == "test@example.com"
        assert mock_create_user.called

    @patch("auth.service.AuthService.get_user_by_email")
    def test_register_existing_user(self, mock_get_user, mock_user):
        """Test registering an existing user returns same response."""
        mock_get_user.return_value = mock_user

        response = client.post(
            "/auth/register", json={"email": "test@example.com", "password": "Password123!"}
        )

        assert response.status_code == 201
        assert response.json()["email"] == "test@example.com"

    @patch("auth.service.AuthService.authenticate_user")
    @patch("auth.service.AuthService.update_last_login")
    def test_login_success(self, mock_update_last_login, mock_authenticate, mock_user):
        """Test successful login."""
        mock_authenticate.return_value = mock_user

        response = client.post(
            "/auth/login", json={"email": "test@example.com", "password": "Password123!"}
        )

        assert response.status_code == 200
        assert "access_token" in response.json()
        assert response.json()["refresh_token"] is None  # Should be in cookie
        assert "refresh_token" in response.cookies
        assert mock_update_last_login.called

    @patch("auth.service.AuthService.authenticate_user")
    def test_login_failure(self, mock_authenticate):
        """Test failed login returns 401."""
        mock_authenticate.return_value = None

        response = client.post(
            "/auth/login", json={"email": "test@example.com", "password": "wrong-password"}
        )

        assert response.status_code == 401

    @patch("auth.service.AuthService.refresh_access_token")
    def test_refresh_token_from_cookie(self, mock_refresh, mock_user):
        """Test token refresh using cookie."""
        mock_token_response = MagicMock()
        mock_token_response.access_token = "new-access-token"
        mock_token_response.refresh_token = "new-refresh-token"
        mock_token_response.token_type = "bearer"
        mock_token_response.expires_in = 3600
        mock_token_response.user = MagicMock(
            id="test-user-123",
            email="test@example.com",
            is_global_admin=False,
            role=None,
            created_at=datetime.now(UTC),
            last_login=None,
        )
        mock_refresh.return_value = mock_token_response

        # Set refresh token cookie
        client.cookies.set("refresh_token", "valid-refresh-token")

        response = client.post("/auth/refresh")

        assert response.status_code == 200
        assert response.json()["access_token"] == "new-access-token"
        assert response.json()["refresh_token"] is None
        assert mock_refresh.called

    @patch("auth.service.AuthService.refresh_access_token")
    def test_refresh_token_invalid(self, mock_refresh):
        """Test refresh with invalid token returns 401."""
        mock_refresh.return_value = None

        client.cookies.set("refresh_token", "invalid-token")

        response = client.post("/auth/refresh")

        assert response.status_code == 401

    @patch("auth.service.get_token_expiry")
    @patch("auth.service.get_token_jti")
    @patch("auth.service.blacklist_service.blacklist_token")
    def test_logout_success(
        self, mock_blacklist, mock_get_jti, mock_get_expiry, mock_user, auth_headers
    ):
        """Test successful logout blacklists token and deletes cookie."""
        mock_get_jti.return_value = "test-jti"
        mock_get_expiry.return_value = datetime.now(UTC) + timedelta(hours=1)

        # Set refresh token cookie
        client.cookies.set("refresh_token", "valid-refresh-token")

        response = client.post("/auth/logout", headers=auth_headers)

        assert response.status_code == 200
        assert mock_blacklist.called
        assert "refresh_token" not in response.cookies

    def test_get_current_user_info(self, mock_user, auth_headers):
        """Test /me endpoint returns current user info."""
        response = client.get("/auth/me", headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["email"] == "test@example.com"

    @patch("auth.service.AuthService.initiate_password_reset")
    def test_forgot_password(self, mock_initiate_reset):
        """Test forgot password always returns same message."""
        mock_initiate_reset.return_value = "reset-token-123"

        response = client.post("/auth/forgot-password", json={"email": "test@example.com"})

        assert response.status_code == 200
        assert "registered" in response.json()["message"]

    @patch("auth.service.AuthService.initiate_password_reset")
    def test_forgot_password_non_existent_email(self, mock_initiate_reset):
        """Test forgot password returns same message for non-existent email."""
        mock_initiate_reset.return_value = None

        response = client.post("/auth/forgot-password", json={"email": "nonexistent@example.com"})

        assert response.status_code == 200
        assert "registered" in response.json()["message"]

    @patch("auth.service.AuthService.reset_password")
    def test_reset_password_success(self, mock_reset_password):
        """Test successful password reset."""
        mock_reset_password.return_value = True

        response = client.post(
            "/auth/reset-password",
            json={"token": "valid-reset-token", "new_password": "NewPass123!"},
        )

        assert response.status_code == 200
        assert "successful" in response.json()["message"]

    @patch("auth.service.AuthService.reset_password")
    def test_reset_password_failure(self, mock_reset_password):
        """Test failed password reset returns 400."""
        mock_reset_password.return_value = False

        response = client.post(
            "/auth/reset-password", json={"token": "invalid-token", "new_password": "NewPass123!"}
        )

        assert response.status_code == 400

    @patch("auth.service.AuthService.change_password")
    def test_change_password_success(self, mock_change_password, mock_user, auth_headers):
        """Test successful password change."""
        mock_change_password.return_value = True

        response = client.post(
            "/auth/change-password",
            json={"current_password": "Password123!", "new_password": "NewPass123!"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert "changed successfully" in response.json()["message"]

    @patch("auth.service.AuthService.change_password")
    def test_change_password_failure(self, mock_change_password, mock_user, auth_headers):
        """Test failed password change returns 400."""
        mock_change_password.return_value = False

        response = client.post(
            "/auth/change-password",
            json={"current_password": "wrong-password", "new_password": "NewPass123!"},
            headers=auth_headers,
        )

        assert response.status_code == 400

    @patch("auth.service.AuthService.list_users")
    def test_list_users_admin(
        self, mock_list_users, mock_admin_user, mock_user, admin_auth_headers
    ):
        """Test admin can list users."""
        mock_list_users.return_value = [mock_admin_user, mock_user]

        response = client.get("/auth/users", headers=admin_auth_headers)

        assert response.status_code == 200
        assert response.json()["total"] == 2

    def test_list_users_non_admin(self, mock_user, auth_headers):
        """Test non-admin cannot list users."""
        # Temporarily override to return regular user instead of admin
        from src.app import app as test_app

        from auth.dependencies import require_global_admin

        # Clear the existing override first
        del test_app.dependency_overrides[require_global_admin]

        # Mock require_global_admin to raise 403
        def mock_require_global_admin(current_user=mock_user):
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Requires global admin privileges",
            )

        test_app.dependency_overrides[require_global_admin] = mock_require_global_admin

        response = client.get("/auth/users", headers=auth_headers)

        assert response.status_code == 403

    @patch("auth.service.AuthService.get_user_by_id")
    def test_get_user_admin(self, mock_get_user, mock_user, mock_admin_user, admin_auth_headers):
        """Test admin can get user by ID."""
        mock_get_user.return_value = mock_user

        response = client.get("/auth/users/test-user-123", headers=admin_auth_headers)

        assert response.status_code == 200
        assert response.json()["email"] == "test@example.com"

    @patch("auth.service.AuthService.delete_user")
    def test_delete_user_admin(self, mock_delete_user, mock_admin_user, admin_auth_headers):
        """Test admin can delete other users."""
        mock_delete_user.return_value = True

        response = client.delete("/auth/users/other-user-789", headers=admin_auth_headers)

        assert response.status_code == 204

    def test_delete_self_admin(self, mock_admin_user, admin_auth_headers):
        """Test admin cannot delete their own account."""
        response = client.delete(f"/auth/users/{mock_admin_user.id}", headers=admin_auth_headers)

        assert response.status_code == 400
        assert "Cannot delete your own account" in response.json()["detail"]

    @patch("auth.service.AuthService.set_global_admin")
    def test_update_global_role(
        self, mock_set_admin, mock_user, mock_admin_user, admin_auth_headers
    ):
        """Test admin can update user's admin status."""
        mock_set_admin.return_value = mock_user

        response = client.put(
            "/auth/users/test-user-123/global-role",
            json={"is_global_admin": True},
            headers=admin_auth_headers,
        )

        assert response.status_code == 200
        assert mock_set_admin.called

    @patch("auth.service.AuthService.reset_password_for_user")
    def test_admin_change_password(self, mock_reset_password, mock_admin_user, admin_auth_headers):
        """Test admin can change any user's password."""
        mock_reset_password.return_value = True

        response = client.post(
            "/auth/users/test-user-123/change-password",
            json={"new_password": "NewAdminPass123!"},
            headers=admin_auth_headers,
        )

        assert response.status_code == 200
        assert mock_reset_password.called
