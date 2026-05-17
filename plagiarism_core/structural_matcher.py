"""Structural matcher for Type 1 (exact) and Type 2 (renamed) plagiarism.

Uses line-level exact and identifier-normalized (shadow) matching,
adapted from detection/line_matcher.py.
"""

from typing import List

from .detection.line_matcher import _line_level_matches
from .detection.line_helpers import _make_shadow_lines
from .models import Match


class StructuralMatcher:
    """Line-level structural matching via exact and shadow line comparison."""

    def __init__(self, min_match_lines: int = 3):
        self.min_match_lines = min_match_lines

    def match(
        self,
        source_a: str,
        source_b: str,
        lang: str = "python",
        tree_a=None,
        bytes_a: bytes = None,
        tree_b=None,
        bytes_b: bytes = None,
    ) -> List[Match]:
        """
        Detect structural matches between two source files.

        Returns list of Match objects of Type 1 (EXACT) or Type 2 (RENAMED).
        """
        # Prepare raw lines and shadow (identifier-normalized) lines
        lines_a = source_a.splitlines()
        lines_b = source_b.splitlines()
        shadow_a = _make_shadow_lines(source_a, lang, tree=tree_a, source_bytes=bytes_a)
        shadow_b = _make_shadow_lines(source_b, lang, tree=tree_b, source_bytes=bytes_b)

        # Use the existing line-level matching algorithm
        matches = _line_level_matches(
            lines_a,
            lines_b,
            shadow_a,
            shadow_b,
            min_match_lines=self.min_match_lines,
            lang_code=lang,
        )
        return matches
