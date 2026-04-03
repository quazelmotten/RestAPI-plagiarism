"""
Exact line matching matcher (Type 1).

Compares lines after normalizing whitespace and stripping comments.
"""

from ..models import Match, PlagiarismType, Point, Region
from ..parsing.parser import ParsedFile
from .base import BaseMatcher


class ExactLineMatcher(BaseMatcher):
    """Matches exact lines (whitespace/comments normalized)."""

    MATCH_TYPE = PlagiarismType.EXACT

    def run(
        self, file_a: ParsedFile, file_b: ParsedFile, covered_a: set[int], covered_b: set[int]
    ) -> list[Match]:
        """
        Find exact line matches between two files.

        Only considers lines that haven't been matched by earlier matchers.
        """
        # Normalize lines: strip whitespace and comments
        lines_a = self._get_normalized_lines(file_a)
        lines_b = self._get_normalized_lines(file_b)

        # Find matching lines using sliding window or hash matching
        matches = self._find_matching_lines(
            lines_a,
            lines_b,
            file_a,
            file_b,
            covered_a,
            covered_b,
            min_length=self.config.min_match_lines,
        )

        # Set plagiarism type
        for m in matches:
            # Override type to EXACT
            object.__setattr__(m, "plagiarism_type", PlagiarismType.EXACT)

        return matches

    def _get_normalized_lines(self, parsed: ParsedFile) -> list[str]:
        """Get whitespace/comments-normalized lines."""
        # Simple approach: split source into lines, strip each
        source = parsed.source_bytes.decode("utf-8", errors="ignore")
        lines = []
        for line in source.splitlines():
            # Strip trailing whitespace but keep indentation significance? For exact matching we should
            # normalize whitespace but not necessarily remove all indentation. But original code used
            # _make_exact_lines which strips leading/trailing whitespace and removes comments.
            stripped = line.strip()
            if stripped:
                # Also remove comments? Original _strip_comments
                stripped = self._strip_comments(stripped, parsed.language)
                lines.append(stripped)
            else:
                lines.append("")
        return lines

    def _strip_comments(self, line: str, lang: str) -> str:
        """Remove single-line comments from a line."""
        # Simple comment stripping based on language
        if lang in ("python", "ruby", "perl", "bash", "shell"):
            comment_idx = line.find("#")
        elif lang in ("sql", "lua"):
            comment_idx = line.find("--")
        else:
            comment_idx = line.find("//")

        if comment_idx != -1:
            # Ensure comment marker not inside string (we'd need more sophisticated parsing)
            # For simplicity, assume comment marker not in string at line level
            line = line[:comment_idx].rstrip()

        return line

    def _find_matching_lines(
        self,
        lines_a: list[str],
        lines_b: list[str],
        file_a: ParsedFile,
        file_b: ParsedFile,
        covered_a: set[int],
        covered_b: set[int],
        min_length: int = 3,
    ) -> list[Match]:
        """
        Find contiguous sequences of matching lines between two files.

        Uses a simple O(n*m) comparison optimized with early exit.
        For large files, could use suffix arrays or fingerprint-based matching.
        """
        matches = []
        n, m = len(lines_a), len(lines_b)

        # Track visited to avoid overlapping matches
        visited_a = set(covered_a)
        visited_b = set(covered_b)

        i = 0
        while i < n:
            # Skip if line i is already covered
            if i in visited_a:
                i += 1
                continue

            j = 0
            while j < m:
                if j in visited_b:
                    j += 1
                    continue

                # Try to extend match starting at i, j
                match_len = 0
                while (
                    i + match_len < n
                    and j + match_len < m
                    and lines_a[i + match_len] == lines_b[j + match_len]
                    and (i + match_len) not in visited_a
                    and (j + match_len) not in visited_b
                ):
                    match_len += 1

                if match_len >= min_length:
                    # Create match
                    match = Match(
                        file1_region=Region(start=Point(i, 0), end=Point(i + match_len - 1, 0)),
                        file2_region=Region(start=Point(j, 0), end=Point(j + match_len - 1, 0)),
                        kgram_count=match_len,  # approximate
                        plagiarism_type=self.MATCH_TYPE,
                        similarity=1.0,
                        description=f"Exact match of {match_len} lines",
                    )
                    matches.append(match)

                    # Mark these lines as temporarily visited for this run (to not overlap within same matcher)
                    for k in range(match_len):
                        visited_a.add(i + k)
                        visited_b.add(j + k)

                    # Skip ahead
                    j += match_len
                else:
                    j += 1
            i += 1

        return matches
