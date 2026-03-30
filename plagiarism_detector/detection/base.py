"""
Base class for matchers in the detection pipeline.
"""

from abc import ABC, abstractmethod
from typing import ClassVar

from ..models import Match, PlagiarismType


class BaseMatcher(ABC):
    """Abstract base class for a plagiarism matcher."""

    # The plagiarism type this matcher produces
    MATCH_TYPE: ClassVar[PlagiarismType]

    def __init__(self, config):
        """
        Initialize matcher with configuration.

        Args:
            config: DetectionConfig object
        """
        self.config = config

    @abstractmethod
    def run(self, file_a, file_b, covered_a: set[int], covered_b: set[int]) -> list[Match]:
        """
        Run the matcher on two files.

        Args:
            file_a: ParsedFile or similar object for first file
            file_b: ParsedFile or similar object for second file
            covered_a: Set of line numbers already matched in file_a
            covered_b: Set of line numbers already matched in file_b

        Returns:
            List of new matches (should not overlap with covered regions)
        """
        pass

    def _is_covered(self, region_lines: set[int], covered: set[int]) -> bool:
        """Check if any line in a region is already covered."""
        return bool(region_lines & covered)

    def _mark_covered(self, matches: list[Match], covered_a: set[int], covered_b: set[int]) -> None:
        """Mark lines from matches as covered."""
        for match in matches:
            covered_a.update(range(match.file1_region.start.line, match.file1_region.end.line + 1))
            covered_b.update(range(match.file2_region.start.line, match.file2_region.end.line + 1))
