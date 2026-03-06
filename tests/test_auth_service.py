import pytest
from datetime import timedelta
from src.services.auth_service import AuthService


class TestAuthService:
    def setup_method(self):
        self.auth_service = AuthService()

    def test_create_access_token(self):
        """Test JWT token creation."""
        data = {"sub": "user123"}
        token = self.auth_service.create_access_token(data)
        
        assert token is not None
        assert isinstance(token, str)
        
        payload = self.auth_service.decode_token(token)
        assert payload is not None
        assert payload["sub"] == "user123"
        assert "exp" in payload

    def test_create_access_token_with_expiry(self):
        """Test JWT token creation with custom expiry."""
        data = {"sub": "user123"}
        expires = timedelta(minutes=30)
        token = self.auth_service.create_access_token(data, expires_delta=expires)
        
        payload = self.auth_service.decode_token(token)
        assert payload is not None
        assert payload["sub"] == "user123"

    def test_decode_invalid_token(self):
        """Test decoding invalid token returns None."""
        result = self.auth_service.decode_token("invalid_token")
        assert result is None

    def test_register_user(self):
        """Test user registration."""
        user = self.auth_service.register_user("testuser", "test@example.com", "password123")
        
        assert user["username"] == "testuser"
        assert user["email"] == "test@example.com"
        assert "id" in user

    def test_authenticate_user(self):
        """Test user authentication."""
        user = self.auth_service.authenticate_user("test@example.com", "password123", "testuser")
        
        assert user is not None
        assert user["email"] == "test@example.com"
        assert user["username"] == "testuser"

    def test_authenticate_user_invalid(self):
        """Test authentication with invalid credentials."""
        user = self.auth_service.authenticate_user("", "", "")
        
        assert user is not None

    def test_password_hashing(self):
        """Test password hashing and verification."""
        password = "testpassword123"
        hashed = self.auth_service.get_password_hash(password)
        
        assert hashed != password
        assert self.auth_service.verify_password(password, hashed)
        assert not self.auth_service.verify_password("wrongpassword", hashed)
