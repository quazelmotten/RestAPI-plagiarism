"""
Renamed identifier line matching matcher (Type 2).

Matches lines after normalizing identifiers to VAR_N placeholders.
"""

from ..normalization.identifiers import normalize_identifiers
from ..parsing.parser import ParsedFile
from .base import BaseMatcher
from ..models import Match, PlagiarismType, Region, Point


class RenamedLineMatcher(BaseMatcher):
    """Matches lines with identifier normalization (Type 2)."""

    MATCH_TYPE = PlagiarismType.RENAMED

    def run(
        self, file_a: ParsedFile, file_b: ParsedFile, covered_a: set[int], covered_b: set[int]
    ) -> list[Match]:
        """
        Find line matches after identifier normalization.

        Produces normalized versions of each file and then finds matching lines.
        """
        # Normalize identifiers globally (per-file scope)
        normalized_a = normalize_identifiers(file_a)
        normalized_b = normalize_identifiers(file_b)

        # Convert to lines
        lines_a = normalized_a.splitlines()
        lines_b = normalized_b.splitlines()

        # Also get per-function normalized? That's for later semantic matching.

        # Find matching lines (similar to exact matcher but on normalized lines)
        matches = self._find_matching_lines(
            lines_a,
            lines_b,
            file_a,
            file_b,
            covered_a,
            covered_b,
            min_length=self.config.min_match_lines,
        )

        # Set type to RENAMED
        for m in matches:
            object.__setattr__(m, "plagiarism_type", PlagiarismType.RENAMED)

        return matches

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
        """Find contiguous matching lines."""
        matches = []
        n, m = len(lines_a), len(lines_b)
        visited_a = set(covered_a)
        visited_b = set(covered_b)

        i = 0
        while i < n:
            if i in visited_a:
                i += 1
                continue

            j = 0
            while j < m:
                if j in visited_b:
                    j += 1
                    continue

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
                    match = Match(
                        file1_region=Region(start=Point(i, 0), end=Point(i + match_len - 1, 0)),
                        file2_region=Region(start=Point(j, 0), end=Point(j + match_len - 1, 0)),
                        kgram_count=match_len,
                        plagiarism_type=self.MATCH_TYPE,
                        similarity=1.0,
                        description=f"Renamed identifier match of {match_len} lines",
                    )
                    matches.append(match)
                    for k in range(match_len):
                        visited_a.add(i + k)
                        visited_b.add(j + k)
                    j += match_len
                else:
                    j += 1
            i += 1

        return matches
