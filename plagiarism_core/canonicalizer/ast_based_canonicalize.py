"""Pure AST-based Type 4 canonicalization - no regex fallbacks."""

import logging

from .ast_canonical import ast_canonicalize

logger = logging.getLogger(__name__)


def canonicalize_type4(code: str, use_ast: bool = True, lang_code: str = "python") -> str:
    """
    Canonicalize code for Type 4 (semantic) plagiarism detection.
    
    This is a pure AST-based implementation - regex fallbacks have been removed.
    If AST parsing fails, we return the original code and let the 
    line-level matching phases handle it.
    """
    if not code or not code.strip():
        return "[empty]"
    
    try:
        return ast_canonicalize(code, lang_code)
    except Exception as e:
        logger.warning("AST canonicalization failed: %s", e)
        return code


def canonicalize_type4_light(code: str, lang_code: str = "python") -> str:
    """
    Lightweight canonicalization for single-line snippets.
    
    Attempts AST-based canonicalization. Falls back to the original code
    if parsing fails.
    """
    return canonicalize_type4(code, use_ast=True, lang_code=lang_code)