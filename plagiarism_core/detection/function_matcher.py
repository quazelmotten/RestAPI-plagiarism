"""Function-level structural matching."""

import logging

from ..canonicalizer import parse_file_once_from_string
from ..models import Match, PlagiarismType
from .ast_helpers import _extract_functions

logger = logging.getLogger(__name__)


def _function_level_matches(
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
    Match functions between files by structural hash (identifiers ignored).

    Produces:
      - Type 3 if the function moved to a different position
      - Type 2 if it stayed in the same position but has different names
    """
    if tree_a is None or bytes_a is None or tree_b is None or bytes_b is None:
        try:
            tree_a, bytes_a = parse_file_once_from_string(source_a, lang_code)
            tree_b, bytes_b = parse_file_once_from_string(source_b, lang_code)
        except Exception:
            logger.warning(
                "Failed to parse sources for function-level matching (lang=%s), skipping",
                lang_code,
                exc_info=True,
            )
            return []

    funcs_a = _extract_functions(tree_a.root_node, bytes_a, lang_code)
    funcs_b = _extract_functions(tree_b.root_node, bytes_b, lang_code)

    # Index B functions by struct hash
    hash_index: dict[int, list[int]] = {}
    for j, f in enumerate(funcs_b):
        if f["struct_hash"]:
            hash_index.setdefault(f["struct_hash"], []).append(j)

    used_b_idx: set[int] = set()
    matches: list[Match] = []

    for _i, fa in enumerate(funcs_a):
        # Skip if already covered by line-level matching
        func_lines_a = set(range(fa["start_line"], fa["end_line"] + 1))
        if func_lines_a & used_lines_a:
            continue
        if not fa["struct_hash"]:
            continue

        candidates = hash_index.get(fa["struct_hash"], [])
        for j in candidates:
            if j in used_b_idx:
                continue
            fb = funcs_b[j]
            func_lines_b = set(range(fb["start_line"], fb["end_line"] + 1))
            if func_lines_b & used_lines_b:
                continue

            # Classify
            is_reordered = abs(fa["start_line"] - fb["start_line"]) > 2
            is_renamed = fa["name"] != fb["name"]

            if is_renamed:
                ptype = PlagiarismType.RENAMED
                desc = f"Function renamed: {fa['name']} → {fb['name']}"
            elif is_reordered:
                ptype = PlagiarismType.REORDERED
                desc = f"Function reordered: {fa['name']}"
            else:
                ptype = PlagiarismType.EXACT
                desc = None

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
                    plagiarism_type=ptype,
                    similarity=1.0,
                    details={"original_name": fa["name"], "renamed_name": fb["name"]}
                    if is_renamed
                    else None,
                    description=desc,
                )
            )
            used_b_idx.add(j)
            break

    return matches
