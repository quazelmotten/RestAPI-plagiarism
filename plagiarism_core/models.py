"""
Core data structures for plagiarism detection.
"""

from dataclasses import dataclass
from typing import TypedDict


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
    plagiarism_type: int = 1
    similarity: float = 1.0
    details: dict | None = None
    description: str | None = None

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
class SimilarityMetrics:
    """Detailed similarity metrics."""

    left_covered: int
    right_covered: int
    left_total: int
    right_total: int
    similarity: float
    longest_fragment: int
    type_coverage: dict[int, float] | None = None


@dataclass
class AnalysisResult:
    """Complete analysis result."""

    similarity_ratio: float
    matches: list[Match]
    metrics: SimilarityMetrics
    file1_path: str
    file2_path: str
    language: str
