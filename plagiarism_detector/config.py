"""
Detection configuration with validated thresholds.
"""

from pydantic import BaseModel, Field


class DetectionConfig(BaseModel):
    """Configuration for plagiarism detection thresholds and parameters."""

    # K-gram fingerprinting
    k: int = Field(3, ge=2, le=10, description="K-gram size for fingerprinting")
    window_size: int = Field(4, ge=2, description="Winnowing window size")

    # Matching thresholds
    min_match_lines: int = Field(3, ge=2, description="Minimum lines for a valid match")
    merge_gap: int = Field(2, ge=0, description="Max line gap to merge adjacent matches")
    semantic_threshold: float = Field(
        0.85, ge=0.5, le=1.0, description="Semantic similarity threshold"
    )

    # Hashing
    hash_base: int = Field(257, ge=2, description="Base for rolling hash")
    hash_mod: int = Field(10**9 + 7, ge=1000, description="Modulus for rolling hash")

    # Performance
    max_file_size: int = Field(10 * 1024 * 1024, ge=1024, description="Max file size in bytes")

    # Detection toggles
    enable_type1: bool = Field(True, description="Enable exact line matching")
    enable_type2: bool = Field(True, description="Enable renamed identifier matching")
    enable_type3: bool = Field(True, description="Enable structural/reordered matching")
    enable_type4: bool = Field(True, description="Enable semantic matching")

    @classmethod
    def default(cls) -> "DetectionConfig":
        """Create default configuration."""
        return cls()

    @classmethod
    def from_dict(cls, data: dict) -> "DetectionConfig":
        """Create from dictionary."""
        return cls(**data)
