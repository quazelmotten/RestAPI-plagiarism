"""
Detection pipeline that orchestrates multiple matchers.

Implements a chain-of-responsibility pattern where matchers run sequentially,
each avoiding regions already covered by previous matchers.
"""

from ..config import DetectionConfig
from ..models import Match
from .base import BaseMatcher
from ..matching import merge_adjacent_matches, resolve_overlaps


class DetectionPipeline:
    """Orchestrates the cascade of matchers."""

    def __init__(self, matchers: list[BaseMatcher], config: DetectionConfig):
        """
        Initialize pipeline.

        Args:
            matchers: Ordered list of matchers (from most specific to most general)
            config: Detection configuration
        """
        self.matchers = matchers
        self.config = config

    def run(self, file_a, file_b) -> list[Match]:
        """
        Run full detection pipeline on two files.

        Args:
            file_a: ParsedFile or comparable object
            file_b: ParsedFile or comparable object

        Returns:
            List of all matches found, sorted and merged appropriately
        """
        # Track which lines are already matched
        covered_a: set[int] = set()
        covered_b: set[int] = set()

        all_matches: list[Match] = []

        # Run each matcher sequentially
        for matcher in self.matchers:
            matches = matcher.run(file_a, file_b, covered_a, covered_b)

            # Filter out matches that are too short
            matches = [
                m for m in matches if m.file1_region.line_count >= self.config.min_match_lines
            ]

            # Add to overall results
            all_matches.extend(matches)

            # Update coverage
            matcher._mark_covered(matches, covered_a, covered_b)

        # Merge adjacent matches of the same type
        merged = merge_adjacent_matches(all_matches, self.config.merge_gap)

        # Remove any remaining overlaps (use interval scheduling)
        final = resolve_overlaps(merged)

        # Sort by position in file_a
        final.sort(key=lambda m: (m.file1_region.start.line, m.file1_region.start.col))

        return final
