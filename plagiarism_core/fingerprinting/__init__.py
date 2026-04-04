"""Fingerprinting: tokenization, winnowing, parsing, and identifier normalization."""

from .core import (
    compute_and_winnow,
    compute_fingerprints,
    index_fingerprints,
    tokenize_and_hash_ast,
    tokenize_with_tree_sitter,
    winnow_fingerprints,
)
from .hashing import stable_hash
from .identifiers import (
    BUILTIN_NAMES,
    _find_function_scopes,
    _make_shadow_lines_scope,
    _normalize_identifiers_in_scope,
    _normalize_in_scope,
    _scope_shadow_hashes,
    _walk,
)
from .languages import (
    LANGUAGE_MAP,
    LanguageProfile,
    get_language,
    get_language_profile,
    get_supported_languages,
    register_language_profile,
)
from .parser import parse_file_once, parse_string_once
from .tokenizer import Token, Tokenizer, tokenize
from .winnow import Fingerprint, Winnower, compute_kgram_hashes

__all__ = [
    "LANGUAGE_MAP",
    "LanguageProfile",
    "get_language",
    "get_language_profile",
    "get_supported_languages",
    "register_language_profile",
    "stable_hash",
    "parse_file_once",
    "parse_string_once",
    "tokenize_with_tree_sitter",
    "tokenize_and_hash_ast",
    "compute_fingerprints",
    "winnow_fingerprints",
    "compute_and_winnow",
    "index_fingerprints",
    "BUILTIN_NAMES",
    "_find_function_scopes",
    "_normalize_in_scope",
    "_walk",
    "_normalize_identifiers_in_scope",
    "_make_shadow_lines_scope",
    "_scope_shadow_hashes",
    "Token",
    "Tokenizer",
    "tokenize",
    "Fingerprint",
    "Winnower",
    "compute_kgram_hashes",
]
