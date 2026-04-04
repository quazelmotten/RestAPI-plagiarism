"""Public API for the canonicalizer package."""

import logging

from .ast_canonical import (
    ast_canonicalize,
    ast_canonicalize_with_identifiers,
)
from .identifier_norm import (
    get_identifier_renames,
    normalize_identifiers,
)
from .legacy_rules import (
    canonicalize_type4,
)

logger = logging.getLogger(__name__)


def canonicalize_full(source: str, lang_code: str = "python", use_ast: bool = True) -> str:
    result = source
    if lang_code == "python":
        result = canonicalize_type4(result, use_ast=use_ast, lang_code=lang_code)
    from ..fingerprinting.identifiers import _normalize_identifiers_in_scope

    result = _normalize_identifiers_in_scope(result, lang_code)
    return result


def parse_file_once_from_string(source: str, lang_code: str = "python") -> tuple:
    from ..fingerprinting.parser import parse_string_once

    return parse_string_once(source, lang_code)


__all__ = [
    "ast_canonicalize",
    "ast_canonicalize_with_identifiers",
    "canonicalize_full",
    "canonicalize_type4",
    "get_identifier_renames",
    "normalize_identifiers",
    "parse_file_once_from_string",
]
