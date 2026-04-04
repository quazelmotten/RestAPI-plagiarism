"""Detection pipeline helpers."""

from ...models import Match


def _mark_covered(covered: set[int], match: Match) -> None:
    for line in range(match.file1["start_line"], match.file1["end_line"] + 1):
        covered.add(line)
    for line in range(match.file2["start_line"], match.file2["end_line"] + 1):
        covered.add(line)
