"""Identifier normalization for Type 2 plagiarism detection."""

import logging
import re

from tree_sitter import Node

logger = logging.getLogger(__name__)


def _get_builtin_names():
    from ..fingerprinting.identifiers import BUILTIN_NAMES

    return BUILTIN_NAMES


def _collect_identifiers(root_node: Node, source_bytes: bytes) -> list[tuple[int, int, str]]:
    identifiers = []
    builtins = _get_builtin_names()

    def visit(node: Node):
        if node.type == "identifier" and not node.children:
            name = source_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="ignore")
            if not (name.startswith("__") and name.endswith("__")) and name not in builtins:
                identifiers.append((node.start_byte, node.end_byte, name))
        for child in node.children:
            visit(child)

    visit(root_node)
    return identifiers


def _assign_placeholders(identifiers: list[tuple[int, int, str]]) -> dict[str, str]:
    seen: dict[str, int] = {}
    for _, _, name in identifiers:
        if name not in seen:
            seen[name] = len(seen)
    return {name: f"VAR_{idx}" for name, idx in seen.items()}


def _replace_identifiers(
    source_bytes: bytes,
    identifiers: list[tuple[int, int, str]],
    placeholders: dict[str, str],
) -> str:
    if not identifiers:
        return source_bytes.decode("utf-8", errors="ignore")
    replacements = []
    for start, end, name in identifiers:
        if name in placeholders:
            replacements.append((start, end, placeholders[name]))
    seen_positions = set()
    unique = []
    for start, end, repl in replacements:
        if start not in seen_positions:
            seen_positions.add(start)
            unique.append((start, end, repl))
    unique.sort(key=lambda x: x[0], reverse=True)
    result = bytearray(source_bytes)
    for start, end, replacement in unique:
        result[start:end] = replacement.encode("utf-8")
    return result.decode("utf-8", errors="ignore")


def _normalize_identifiers_from_tree(tree, source_bytes: bytes, fallback: str) -> str:
    identifiers = _collect_identifiers(tree.root_node, source_bytes)
    if not identifiers:
        return fallback
    placeholders = _assign_placeholders(identifiers)
    return _replace_identifiers(source_bytes, identifiers, placeholders)


def normalize_identifiers(source: str, lang_code: str = "python") -> str:
    try:
        tree, source_bytes = _parse_string_once(source, lang_code)
    except Exception:
        logger.warning(
            "Failed to parse source for identifier normalization (lang=%s), returning original",
            lang_code,
            exc_info=True,
        )
        return source
    return _normalize_identifiers_from_tree(tree, source_bytes, source)


def get_identifier_renames(source_a: str, source_b: str, lang_code: str = "python") -> list[dict]:
    try:
        tree_a, bytes_a = _parse_string_once(source_a, lang_code)
        tree_b, bytes_b = _parse_string_once(source_b, lang_code)
    except Exception:
        logger.warning(
            "Failed to parse sources for rename detection (lang=%s), returning empty",
            lang_code,
            exc_info=True,
        )
        return []
    ids_a = _collect_identifiers(tree_a.root_node, bytes_a)
    ids_b = _collect_identifiers(tree_b.root_node, bytes_b)
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
    source_lines_a = source_a.split("\n")
    for i in range(min(len(order_a), len(order_b))):
        if order_a[i] != order_b[i]:
            line_num = _find_line_for_name(source_lines_a, order_a[i])
            renames.append(
                {
                    "original": order_a[i],
                    "renamed": order_b[i],
                    "line": line_num,
                }
            )
    return renames


def _find_line_for_name(lines: list[str], name: str) -> int:
    pattern = re.compile(r"\b" + re.escape(name) + r"\b")
    for i, line in enumerate(lines):
        if pattern.search(line):
            return i + 1
    return 1


def _parse_string_once(source, lang_code):
    from ..fingerprinting.parser import parse_string_once

    return parse_string_once(source, lang_code)
