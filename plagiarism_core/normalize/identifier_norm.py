"""Identifier normalization for Type 2 plagiarism detection."""

from typing import List, Tuple
from tree_sitter import Node

from ..parser import parse_string
from ..parser import get_language_profile


def _collect_identifiers(root_node: Node, source_bytes: bytes, builtins: set[str]) -> List[Tuple[int, int, str]]:
    """Collect all user-defined identifiers (non-builtin, non-dunder)."""
    identifiers = []

    def visit(node: Node):
        if node.type == "identifier" and not node.children:
            name = source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="ignore")
            if not (name.startswith("__") and name.endswith("__")) and name not in builtins:
                identifiers.append((node.start_byte, node.end_byte, name))
        for child in node.children:
            visit(child)

    visit(root_node)
    return identifiers


def _assign_placeholders(identifiers: List[Tuple[int, int, str]]) -> dict[str, str]:
    """Assign VAR_0, VAR_1, ... in order of first appearance."""
    seen = {}
    for _, _, name in identifiers:
        if name not in seen:
            seen[name] = len(seen)
    return {name: f"VAR_{idx}" for name, idx in seen.items()}


def _replace_identifiers(source_bytes: bytes, identifiers: List[Tuple[int, int, str]], placeholders: dict[str, str]) -> str:
    """Replace all identifier occurrences with placeholders."""
    if not identifiers:
        return source_bytes.decode("utf-8", errors="ignore")
    replacements = []
    for start, end, name in identifiers:
        if name in placeholders:
            replacements.append((start, end, placeholders[name]))
    # Deduplicate by start position (each identifier position appears multiple times in identifier list)
    seen_pos = set()
    unique = []
    for start, end, repl in replacements:
        if start not in seen_pos:
            seen_pos.add(start)
            unique.append((start, end, repl))
    unique.sort(key=lambda x: x[0], reverse=True)
    result = bytearray(source_bytes)
    for start, end, repl in unique:
        result[start:end] = repl.encode("utf-8")
    return result.decode("utf-8", errors="ignore")


def normalize_identifiers(source: str, lang: str = "python") -> str:
    """Replace all user-defined identifiers with VAR_N placeholders."""
    try:
        profile = get_language_profile(lang)
        builtins = profile.builtin_names
    except Exception:
        builtins = set()
    try:
        tree, source_bytes = parse_string(source, lang)
        identifiers = _collect_identifiers(tree.root_node, source_bytes, builtins)
        placeholders = _assign_placeholders(identifiers)
        return _replace_identifiers(source_bytes, identifiers, placeholders)
    except Exception:
        return source


def _find_line_for_name(lines: List[str], name: str) -> int:
    """Find the line number (1-indexed) where name first appears."""
    import re

    pattern = re.compile(r"\b" + re.escape(name) + r"\b")
    for i, line in enumerate(lines):
        if pattern.search(line):
            return i + 1
    return 1


def get_identifier_renames(source_a: str, source_b: str, lang: str = "python") -> List[dict]:
    """
    Detect identifier renaming between two code snippets.

    Returns list of dicts: {"original": name_a, "renamed": name_b, "line": line_num}
    Only includes mismatches in order (assuming same order of first appearances).
    """
    try:
        profile = get_language_profile(lang)
        builtins = profile.builtin_names
    except Exception:
        builtins = set()
    try:
        tree_a, bytes_a = parse_string(source_a, lang)
        tree_b, bytes_b = parse_string(source_b, lang)
    except Exception:
        return []
    ids_a = _collect_identifiers(tree_a.root_node, bytes_a, builtins)
    ids_b = _collect_identifiers(tree_b.root_node, bytes_b, builtins)
    # Determine first-appearance order
    order_a = []
    seen = set()
    for _, _, name in ids_a:
        if name not in seen:
            seen.add(name)
            order_a.append(name)
    order_b = []
    seen = set()
    for _, _, name in ids_b:
        if name not in seen:
            seen.add(name)
            order_b.append(name)
    renames = []
    lines_a = source_a.splitlines()
    for i in range(min(len(order_a), len(order_b))):
        if order_a[i] != order_b[i]:
            line_num = _find_line_for_name(lines_a, order_a[i])
            renames.append({"original": order_a[i], "renamed": order_b[i], "line": line_num})
    return renames
