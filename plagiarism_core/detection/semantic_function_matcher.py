"""Semantic function matching."""

import logging

from ..canonicalizer import parse_file_once_from_string
from ..models import Match, PlagiarismType
from .ast_helpers import _extract_functions

logger = logging.getLogger(__name__)


def _semantic_function_matches(
    source_a: str,
    source_b: str,
    used_lines_a: set[int],
    used_lines_b: set[int],
    lang_code: str = "python",
    tree_a=None,
    bytes_a: bytes = None,
    tree_b=None,
    bytes_b: bytes = None,
) -> list[Match]:
    """
    Apply Type 4 semantic matching at the function level.

    Uses AST-level semantic normalization (Approach A): semantically equivalent
    constructs (for/while loops, comprehensions, f-strings, etc.) produce identical
    semantic hashes, enabling detection even when the structural hashes differ.

    For each unmatched function in A, tries to find a function in B that:
      1. Didn't match at any earlier level
      2. Has the same SEMANTIC hash (different from structural hash)
    """
    if tree_a is None or bytes_a is None or tree_b is None or bytes_b is None:
        try:
            tree_a, bytes_a = parse_file_once_from_string(source_a, lang_code)
            tree_b, bytes_b = parse_file_once_from_string(source_b, lang_code)
        except Exception:
            logger.warning(
                "Failed to parse sources for semantic function matching (lang=%s), skipping",
                lang_code,
                exc_info=True,
            )
            return []

    funcs_a = _extract_functions(tree_a.root_node, bytes_a, lang_code)
    funcs_b = _extract_functions(tree_b.root_node, bytes_b, lang_code)

    # Index B functions by semantic hash (not structural hash)
    # This catches semantically equivalent code that structurally differs
    sem_b_hashes: dict[int, list[int]] = {}
    for j, fb in enumerate(funcs_b):
        if fb["semantic_hash"]:
            sem_b_hashes.setdefault(fb["semantic_hash"], []).append(j)

    used_b_idx: set[int] = set()
    matches: list[Match] = []

    for _i, fa in enumerate(funcs_a):
        func_lines_a = set(range(fa["start_line"], fa["end_line"] + 1))
        if func_lines_a & used_lines_a:
            continue
        if not fa["semantic_hash"]:
            continue

        candidates = sem_b_hashes.get(fa["semantic_hash"], [])
        for j in candidates:
            if j in used_b_idx:
                continue
            fb = funcs_b[j]
            func_lines_b = set(range(fb["start_line"], fb["end_line"] + 1))
            if func_lines_b & used_lines_b:
                continue

            # Allow semantic matching when struct hashes differ
            # (e.g., augmented assignment vs explicit assignment)
            # Skip if struct hashes are the same AND semantic hashes are the same
            # (those would be caught by function-level matching)
            if fa["struct_hash"] == fb["struct_hash"]:
                continue

            matches.append(
                Match(
                    file1={
                        "start_line": fa["start_line"],
                        "start_col": 0,
                        "end_line": fa["end_line"],
                        "end_col": 0,
                    },
                    file2={
                        "start_line": fb["start_line"],
                        "start_col": 0,
                        "end_line": fb["end_line"],
                        "end_col": 0,
                    },
                    kgram_count=fa["end_line"] - fa["start_line"] + 1,
                    plagiarism_type=PlagiarismType.SEMANTIC,
                    similarity=1.0,
                    details={
                        "original_function": fa["name"],
                        "matched_function": fb["name"],
                    },
                    description=f"Semantic equivalent: {fa['name']} ↔ {fb['name']}",
                )
            )
            used_b_idx.add(j)
            break

    return matches
