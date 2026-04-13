"""Authentication configuration."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthConfig(BaseSettings):
    """Authentication settings."""

    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Initial admin creation
    initial_admin_email: str = Field(default="", validation_alias="INITIAL_ADMIN_EMAIL")
    initial_admin_password: str = Field(default="", validation_alias="INITIAL_ADMIN_PASSWORD")

    # Password validation
    min_password_length: int = Field(default=8, validation_alias="MIN_PASSWORD_LENGTH")
    require_uppercase: bool = Field(default=True, validation_alias="REQUIRE_UPPERCASE")
    require_lowercase: bool = Field(default=True, validation_alias="REQUIRE_LOWERCASE")
    require_digit: bool = Field(default=True, validation_alias="REQUIRE_DIGIT")

    # Token settings
    access_token_expire_minutes: int = Field(
        default=1440, validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES"
    )  # 24 hours
    refresh_token_expire_days: int = Field(default=7, validation_alias="REFRESH_TOKEN_EXPIRE_DAYS")


# Global config instance
auth_config = AuthConfig()
