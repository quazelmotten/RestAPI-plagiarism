"""Match merging utilities."""

from ..models import Match


def _merge_matches(matches: list[Match], gap: int = 0) -> list[Match]:
    """
    Merge adjacent matches that are of the SAME plagiarism type.

    Only merges matches with identical plagiarism_type to avoid
    swallowing Type 4 (semantic) lines into surrounding Type 1 (exact) regions.
    """
    if not matches:
        return []

    matches = sorted(matches, key=lambda m: (m.file1["start_line"], m.file2["start_line"]))
    merged = [
        Match(
            file1=dict(matches[0].file1),
            file2=dict(matches[0].file2),
            kgram_count=matches[0].kgram_count,
            plagiarism_type=matches[0].plagiarism_type,
            similarity=matches[0].similarity,
            details=matches[0].details,
            description=matches[0].description,
        )
    ]

    for m in matches[1:]:
        prev = merged[-1]
        f1_adj = m.file1["start_line"] <= prev.file1["end_line"] + gap + 1
        f2_adj = m.file2["start_line"] <= prev.file2["end_line"] + gap + 1
        same_type = m.plagiarism_type == prev.plagiarism_type

        if f1_adj and f2_adj and same_type:
            prev.file1["end_line"] = max(prev.file1["end_line"], m.file1["end_line"])
            prev.file2["end_line"] = max(prev.file2["end_line"], m.file2["end_line"])
            prev.kgram_count += m.kgram_count
            # Merge details
            if m.details:
                if prev.details:
                    for k, v in m.details.items():
                        if (
                            k in prev.details
                            and isinstance(prev.details[k], list)
                            and isinstance(v, list)
                        ):
                            prev.details[k].extend(v)
                        else:
                            prev.details[k] = v
                else:
                    prev.details = m.details
        else:
            merged.append(
                Match(
                    file1=dict(m.file1),
                    file2=dict(m.file2),
                    kgram_count=m.kgram_count,
                    plagiarism_type=m.plagiarism_type,
                    similarity=m.similarity,
                    details=m.details,
                    description=m.description,
                )
            )

    return merged


def _covered_lines(matches: list[Match], is_file1: bool) -> set[int]:
    """Get the set of covered line indices (0-indexed) from matches."""
    covered: set[int] = set()
    for m in matches:
        region = m.file1 if is_file1 else m.file2
        for line in range(region["start_line"], region["end_line"] + 1):
            covered.add(line)
    return covered
