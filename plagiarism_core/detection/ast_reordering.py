"""AST-based reordering detection for Type 3 plagiarism.

Compares top-level function/class definitions across two files using
tree-sitter ASTs. If the same definitions exist in both files but in
a different order, they are flagged as REORDERED.
"""

import hashlib

from ..fingerprinting.parser import parse_string_once
from ..fingerprinting.languages import get_language_profile
from ..canonicalizer import normalize_identifiers
from ..models import Match, PlagiarismType


def detect_ast_reordering(source_a: str, source_b: str, lang: str = "python") -> list[Match]:
    """Detect function/class reordering between two files.

    Extracts top-level function and class definitions from both files,
    normalizes their source (identifier-agnostic), and checks if the same
    definitions appear in both files but in different order.

    Returns a list of REORDERED Match objects (one per matched declaration),
    or an empty list if no reordering is detected.
    """
    if not source_a.strip() or not source_b.strip():
        return []

    tree_a, bytes_a = parse_string_once(source_a, lang)
    tree_b, bytes_b = parse_string_once(source_b, lang)

    profile = get_language_profile(lang)
    func_types = set(profile.function_node_types)
    class_types = set(profile.class_node_types)
    all_types = func_types | class_types

    def _extract(root, src_bytes, src_text):
        """Extract top-level function/class definitions."""
        decls = []
        for child in root.children:
            node = child
            if child.type == "decorated_definition":
                for sub in child.children:
                    if sub.type in func_types:
                        node = sub
                        break
                else:
                    continue
            elif child.type not in all_types:
                continue

            start_line = node.start_point[0]
            end_line = node.end_point[0]
            raw_text = src_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="ignore")
            normalized = normalize_identifiers(raw_text, lang)
            h = hashlib.md5(normalized.encode()).hexdigest()
            decls.append({
                "start_line": start_line,
                "end_line": end_line,
                "hash": h,
            })
        return decls

    decls_a = _extract(tree_a.root_node, bytes_a, source_a)
    decls_b = _extract(tree_b.root_node, bytes_b, source_b)

    if len(decls_a) < 2 or len(decls_b) < 2:
        return []

    hash_to_a: dict[str, list[int]] = {}
    for i, d in enumerate(decls_a):
        hash_to_a.setdefault(d["hash"], []).append(i)

    matches = []
    used_a: set[int] = set()
    for b_idx, d in enumerate(decls_b):
        if d["hash"] in hash_to_a:
            for a_idx in hash_to_a[d["hash"]]:
                if a_idx not in used_a:
                    matches.append((a_idx, b_idx))
                    used_a.add(a_idx)
                    break

    if len(matches) < 2:
        return []

    matches_sorted = sorted(matches, key=lambda m: m[0])
    b_in_order = all(
        matches_sorted[i][1] < matches_sorted[i + 1][1]
        for i in range(len(matches_sorted) - 1)
    )

    if b_in_order:
        return []

    result = []
    for a_idx, b_idx in matches:
        da = decls_a[a_idx]
        db = decls_b[b_idx]
        result.append(Match(
            file1={"start_line": da["start_line"], "start_col": 0,
                   "end_line": da["end_line"], "end_col": 0},
            file2={"start_line": db["start_line"], "start_col": 0,
                   "end_line": db["end_line"], "end_col": 0},
            kgram_count=da["end_line"] - da["start_line"] + 1,
            plagiarism_type=PlagiarismType.REORDERED,
            similarity=1.0,
            details=None,
            description="AST reordering: function/class definition reordered",
        ))
    return result
