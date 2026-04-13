"""
Plagiarism detection configuration.
"""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class PlagiarismConfig(BaseSettings):
    """Settings for plagiarism detection algorithm."""

    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Detection thresholds
    default_threshold: float = Field(default=0.75, validation_alias="DEFAULT_PLAGIARISM_THRESHOLD")
    inverted_index_min_overlap: float = Field(
        default=0.15, validation_alias="INVERTED_INDEX_MIN_OVERLAP_THRESHOLD"
    )

    # Supported programming languages
    supported_languages: str = Field(
        default="python,java,cpp,c,javascript", validation_alias="SUPPORTED_LANGUAGES"
    )

    # File size limits
    max_file_size: int = Field(default=1048576, validation_alias="MAX_FILE_SIZE")  # 1MB
    max_files_per_batch: int = Field(default=100, validation_alias="MAX_FILES_PER_BATCH")
    max_upload_request_size: int = Field(
        default=52428800, validation_alias="MAX_UPLOAD_REQUEST_SIZE"
    )  # 50MB

    @field_validator("default_threshold")
    @classmethod
    def validate_threshold(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("Threshold must be between 0.0 and 1.0")
        return v

    @field_validator("inverted_index_min_overlap")
    @classmethod
    def validate_overlap(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("Overlap threshold must be between 0.0 and 1.0")
        return v

    @property
    def supported_languages_list(self) -> list[str]:
        """Parse supported languages into list."""
        return [lang.strip().lower() for lang in self.supported_languages.split(",")]
