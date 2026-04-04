"""
Core data structures for plagiarism detection.
"""

from dataclasses import dataclass
from enum import IntEnum
from typing import TypedDict


class PlagiarismType(IntEnum):
    """Classification of detected plagiarism."""

    NONE = 0
    EXACT = 1
    RENAMED = 2
    REORDERED = 3
    SEMANTIC = 4


PLAGIARISM_TYPE_LABELS = {
    PlagiarismType.NONE: "No match",
    PlagiarismType.EXACT: "Exact copy",
    PlagiarismType.RENAMED: "Renamed identifiers",
    PlagiarismType.REORDERED: "Reordered code",
    PlagiarismType.SEMANTIC: "Semantic equivalent",
}


@dataclass(frozen=True)
class Point:
    """Zero-indexed position in source code."""

    line: int
    col: int


@dataclass(frozen=True)
class Region:
    """Rectangular span of source code."""

    start: Point
    end: Point

    @property
    def line_count(self) -> int:
        return self.end.line - self.start.line + 1


class SourceRegion(TypedDict):
    """Typed dict for match region coordinates."""

    start_line: int
    start_col: int
    end_line: int
    end_col: int


@dataclass
class Match:
    """A matching region between two files."""

    file1: SourceRegion
    file2: SourceRegion
    kgram_count: int
    plagiarism_type: int = PlagiarismType.EXACT
    similarity: float = 1.0
    details: dict | None = None
    description: str | None = None

    # New-style Region-based access
    @property
    def file1_region(self) -> Region:
        return Region(
            start=Point(line=self.file1["start_line"], col=self.file1["start_col"]),
            end=Point(line=self.file1["end_line"], col=self.file1["end_col"]),
        )

    @property
    def file2_region(self) -> Region:
        return Region(
            start=Point(line=self.file2["start_line"], col=self.file2["start_col"]),
            end=Point(line=self.file2["end_line"], col=self.file2["end_col"]),
        )


@dataclass
class FunctionInfo:
    """Extracted function with structural and semantic hashes."""

    name: str
    qualified_name: str
    region: Region
    structural_hash: int
    semantic_hash: int


@dataclass
class SimilarityMetrics:
    """Detailed similarity metrics."""

    left_covered: int
    right_covered: int
    left_total: int
    right_total: int
    similarity: float
    longest_fragment: int


@dataclass
class AnalysisResult:
    """Complete analysis result."""

    similarity_ratio: float
    matches: list[Match]
    metrics: SimilarityMetrics
    file1_path: str
    file2_path: str
    language: str
