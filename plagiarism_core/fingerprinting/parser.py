"""Parser helpers for tree-sitter."""

from typing import Any

from tree_sitter import Parser

from .languages import get_language


def parse_file_once(file_path: str, lang_code: str = "python") -> tuple[Any, bytes]:
    """
    Parse a file once with tree-sitter, returning the tree and source bytes.

    Use this to avoid re-parsing the same file for tokenization and AST hashing.
    Pass the returned tree to tokenize_with_tree_sitter() and extract_ast_hashes().
    """
    language = get_language(lang_code)
    parser = Parser(language)

    with open(file_path, encoding="utf-8", errors="ignore") as f:
        code = f.read()

    source_bytes = code.encode("utf-8")
    tree = parser.parse(source_bytes)
    return tree, source_bytes


def parse_string_once(source: str, lang_code: str = "python") -> tuple[Any, bytes]:
    """Parse a source code string with tree-sitter. Returns (tree, source_bytes)."""
    language = get_language(lang_code)
    parser = Parser(language)
    source_bytes = source.encode("utf-8")
    tree = parser.parse(source_bytes)
    return tree, source_bytes
