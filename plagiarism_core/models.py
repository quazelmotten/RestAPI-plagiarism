"""
Core data structures for plagiarism detection.
"""

from dataclasses import dataclass
from typing import List, Tuple, Dict, Any, Optional


@dataclass
class Fingerprint:
    """A winnowed fingerprint representing a code fragment."""
    hash: int
    start: Tuple[int, int]  # (line, col)
    end: Tuple[int, int]    # (line, col)
    kgram_idx: int = 0


@dataclass
class Token:
    """A syntax token from tree-sitter."""
    type: str
    start: Tuple[int, int]
    end: Tuple[int, int]


@dataclass
class Match:
    """A matching region between two files."""
    file1: Dict[str, Any]  # {'start_line', 'start_col', 'end_line', 'end_col'}
    file2: Dict[str, Any]
    kgram_count: int


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
    matches: List[Match]
    metrics: SimilarityMetrics
    file1_path: str
    file2_path: str
    language: str
