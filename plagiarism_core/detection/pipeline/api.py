"""detect_plagiarism orchestrator."""

import logging

from ..line_matcher import _line_level_matches
from ..merge_helpers import _merge_matches
from ..semantic_line_matcher import _semantic_line_matches
from .helpers import merge_matches_with_confidence
from .phase1 import run_phase1
from .phase2 import run_phase2
from .prep import prepare_sources

logger = logging.getLogger(__name__)


def detect_plagiarism(
    source_a,
    source_b,
    lang_code="python",
    min_match_lines=2,
    embeddings_a: dict | None = None,  # func_name -> embedding
    embeddings_b: dict | None = None,  # func_name -> embedding
):
    """
    Detect plagiarism between two source code strings.

    Args:
        source_a, source_b: Source code strings
        lang_code: Programming language
        min_match_lines: Minimum lines for a match
        embeddings_a, embeddings_b: Optional dicts mapping function names to embeddings
                                (from F2LLM-v2-80M)

    Returns:
        List of Match objects with plagiarism types and confidence scores
    """
    lines_a, lines_b, tree_a, bytes_a, tree_b, bytes_b, shadow_a, shadow_b = prepare_sources(
        source_a, source_b, lang_code
    )

    all_matches = []
    covered_a = set()
    covered_b = set()

    if tree_a and tree_b:
        all_matches = run_phase1(
            lines_a,
            lines_b,
            shadow_a,
            shadow_b,
            covered_a,
            covered_b,
            lang_code,
            tree_a,
            bytes_a,
            tree_b,
            bytes_b,
            embeddings_a=embeddings_a,
            embeddings_b=embeddings_b,
        )
        run_phase2(
            all_matches,
            lines_a,
            lines_b,
            shadow_a,
            shadow_b,
            covered_a,
            covered_b,
            min_match_lines,
            lang_code,
        )

    _run_phase3(
        all_matches, lines_a, lines_b, shadow_a, shadow_b, covered_a, covered_b, min_match_lines, lang_code
    )
    _run_phase4(
        all_matches,
        source_a,
        source_b,
        covered_a,
        covered_b,
        lines_a,
        lines_b,
        shadow_a,
        shadow_b,
        min_match_lines,
        lang_code,
    )

    # Merge adjacent same-type matches
    all_matches = _merge_matches(all_matches, gap=0)

    # Remove contained matches (smaller matches inside larger ones)
    all_matches = _filter_contained_matches(all_matches)

    # Post-process with confidence-based enrichment (doesn't drop matches)
    all_matches = merge_matches_with_confidence(all_matches)

    all_matches.sort(key=lambda m: m.file1["start_line"])

    return all_matches


def _filter_contained_matches(matches: list) -> list:
    """Remove matches fully contained within larger matches."""
    if not matches:
        return matches

    # Sort by size (largest first) - keep larger matches
    ranges = []
    for m in matches:
        a_size = m.file1["end_line"] - m.file1["start_line"]
        b_size = m.file2["end_line"] - m.file2["start_line"]
        ranges.append({
            'match': m,
            'a_start': m.file1["start_line"],
            'a_end': m.file1["end_line"],
            'b_start': m.file2["start_line"],
            'b_end': m.file2["end_line"],
            'size': a_size + b_size,
        })

    ranges.sort(key=lambda x: -x['size'])

    filtered = []
    used_a = set()
    used_b = set()

    for r in ranges:
        a_range = set(range(r['a_start'], r['a_end'] + 1))
        b_range = set(range(r['b_start'], r['b_end'] + 1))

        # Check if fully contained in existing matches (both files)
        if a_range.issubset(used_a) and b_range.issubset(used_b):
            # Keep if it's a different type (e.g., RENAMED inside EXACT is valuable)
            existing_types = set()
            for existing in filtered:
                existing_range = set(range(existing.file1['start_line'], existing.file1['end_line'] + 1))
                if a_range.issubset(existing_range):
                    existing_types.add(existing.plagiarism_type)

            if r['match'].plagiarism_type not in existing_types:
                # Different type - keep it
                filtered.append(r['match'])
                used_a.update(a_range)
                used_b.update(b_range)
            continue

        filtered.append(r['match'])
        used_a.update(a_range)
        used_b.update(b_range)

    filtered.sort(key=lambda m: m.file1["start_line"])
    return filtered


def _run_phase3(
    all_matches, lines_a, lines_b, shadow_a, shadow_b, covered_a, covered_b, min_match_lines, lang_code
):
    module_line_matches = _line_level_matches(lines_a, lines_b, shadow_a, shadow_b, min_match_lines, lang_code)
    for m in module_line_matches:
        a_range = set(range(m.file1["start_line"], m.file1["end_line"] + 1))
        b_range = set(range(m.file2["start_line"], m.file2["end_line"] + 1))
        new_a = a_range - covered_a
        new_b = b_range - covered_b

        new_a_size = len(new_a)
        new_b_size = len(new_b)

        # Only add if there's meaningful new coverage on either side (min 2 lines)
        min_new_lines = 2
        if new_a_size >= min_new_lines or new_b_size >= min_new_lines:
            # Create copies to avoid modifying original match
            import copy
            new_match = copy.deepcopy(m)

            # Set range to cover only new lines
            if new_a_size >= min_new_lines:
                new_a_range = sorted(new_a)
                new_match.file1["start_line"] = new_a_range[0]
                new_match.file1["end_line"] = new_a_range[-1]
            if new_b_size >= min_new_lines:
                new_b_range = sorted(new_b)
                new_match.file2["start_line"] = new_b_range[0]
                new_match.file2["end_line"] = new_b_range[-1]

            # Set kgram_count to actual new lines
            new_match.kgram_count = min(new_a_size, new_b_size) if new_a_size and new_b_size else max(new_a_size, new_b_size)

            all_matches.append(new_match)
            covered_a.update(new_a)
            covered_b.update(new_b)


def _run_phase4(
    all_matches,
    source_a,
    source_b,
    covered_a,
    covered_b,
    lines_a,
    lines_b,
    shadow_a,
    shadow_b,
    min_match_lines,
    lang_code,
):
    sem_line_matches = _semantic_line_matches(
        source_a,
        source_b,
        covered_a,
        covered_b,
        lines_a,
        lines_b,
        shadow_a,
        shadow_b,
        min_match_lines=1,
        lang_code=lang_code,
        func_matches=all_matches,
    )
    all_matches.extend(sem_line_matches)


def detect_plagiarism_from_files(file_a, file_b, lang_code="python", min_match_lines=2):
    with open(file_a, encoding="utf-8", errors="ignore") as f:
        source_a = f.read()
    with open(file_b, encoding="utf-8", errors="ignore") as f:
        source_b = f.read()
    return detect_plagiarism(source_a, source_b, lang_code, min_match_lines)
