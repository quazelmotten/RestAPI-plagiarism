"""Normalization modules: identifier normalization and semantic canonicalization."""

from .identifier_norm import normalize_identifiers, get_identifier_renames
from .ast_canonical import ast_canonicalize, canonicalize_type4, canonicalize_type4_light

__all__ = [
    "normalize_identifiers",
    "get_identifier_renames",
    "ast_canonicalize",
    "canonicalize_type4",
    "canonicalize_type4_light",
]
