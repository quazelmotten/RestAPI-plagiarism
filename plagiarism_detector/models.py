"""
Core data structures for plagiarism detection using frozen dataclasses.
"""

from dataclasses import dataclass
from enum import IntEnum
from typing import Any


class PlagiarismType(IntEnum):
    """Classification of detected plagiarism."""

    NONE = 0  # No match
    EXACT = 1  # Exact copy (whitespace/comments may differ)
    RENAMED = 2  # Same code structure, different identifiers
    REORDERED = 3  # Same code units in different order
    SEMANTIC = 4  # Semantically equivalent (for↔while, etc.)


PLAGIARISM_TYPE_LABELS = {
    PlagiarismType.NONE: "No match",
    PlagiarismType.EXACT: "Exact copy",
    PlagiarismType.RENAMED: "Renamed identifiers",
    PlagiarismType.REORDERED: "Reordered code",
    PlagiarismType.SEMANTIC: "Semantic equivalent",
}


@dataclass(frozen=True)
class Point:
    """A position in source code (line, column)."""

    line: int  # 0-indexed
    col: int  # 0-indexed


@dataclass(frozen=True)
class Region:
    """A rectangular region in source code."""

    start: Point
    end: Point

    @property
    def line_count(self) -> int:
        """Number of lines spanned by this region."""
        return self.end.line - self.start.line + 1


@dataclass(frozen=True)
class Match:
    """A matching region between two files."""

    file1_region: Region
    file2_region: Region
    kgram_count: int
    plagiarism_type: PlagiarismType
    similarity: float = 1.0
    details: dict[str, Any] | None = None
    description: str | None = None


@dataclass(frozen=True)
class SimilarityMetrics:
    """Detailed similarity metrics."""

    left_covered: int
    right_covered: int
    left_total: int
    right_total: int
    similarity: float
    longest_fragment: int


@dataclass(frozen=True)
class AnalysisResult:
    """Complete analysis result."""

    similarity_ratio: float
    matches: list[Match]
    metrics: SimilarityMetrics
    file1_path: str
    file2_path: str
    language: str


@dataclass(frozen=True)
class FunctionInfo:
    """Information about a function or method extracted from source."""

    name: str
    qualified_name: str
    region: Region
    structural_hash: str
    semantic_hash: str
    node: Any  # tree-sitter Node (not serializable)


@dataclass(frozen=True)
class Token:
    """A token extracted from source for fingerprinting."""

    type: str  # token type (identifier, operator, literal, etc.)
    value: str
    line: int
    col: int


@dataclass(frozen=True)
class Fingerprint:
    """A k-gram fingerprint with hash and positions."""

    hash_value: int
    positions: list[int]  # line numbers where this k-gram appears
    token_count: int
