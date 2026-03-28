"""
Storage configuration.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class StorageConfig(BaseSettings):
    """Storage settings for file uploads."""

    model_config = SettingsConfigDict(
        env_prefix="STORAGE_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    local_path: str = Field(default="/app/s3_storage", validation_alias="STORAGE_LOCAL_PATH")
    bucket_name: str = Field(default="plagiarism-bucket", validation_alias="BUCKET_NAME")
