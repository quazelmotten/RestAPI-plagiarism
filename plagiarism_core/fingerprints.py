"""
Tokenization and fingerprinting for plagiarism detection.

This module re-exports public symbols from the fingerprinting package
for backward compatibility.
"""

from .fingerprinting import (
    BUILTIN_NAMES,
    LANGUAGE_MAP,
    Fingerprint,
    Token,
    Tokenizer,
    Winnower,
    compute_and_winnow,
    compute_fingerprints,
    compute_kgram_hashes,
    get_language,
    index_fingerprints,
    parse_file_once,
    parse_string_once,
    stable_hash,
    tokenize,
    tokenize_and_hash_ast,
    tokenize_with_tree_sitter,
    winnow_fingerprints,
)

__all__ = [
    "BUILTIN_NAMES",
    "LANGUAGE_MAP",
    "Token",
    "Tokenizer",
    "Winnower",
    "compute_and_winnow",
    "compute_fingerprints",
    "compute_kgram_hashes",
    "get_language",
    "index_fingerprints",
    "parse_file_once",
    "parse_string_once",
    "stable_hash",
    "tokenize",
    "tokenize_and_hash_ast",
    "tokenize_with_tree_sitter",
    "winnow_fingerprints",
    "Fingerprint",
]
