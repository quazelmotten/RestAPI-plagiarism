"""
Code canonicalization for plagiarism type detection.

Thin re-exporter for backward compatibility.
See canonicalizer/ subpackage for the implementation.
"""

from .canonicalizer import (
    SEMANTIC_NODE_MAP as SEMANTIC_NODE_MAP,
)
from .canonicalizer import (
    _emit_canonical as _emit_canonical,
)
from .canonicalizer import (
    _emit_semantic_node as _emit_semantic_node,
)
from .canonicalizer import (
    _extract_return_value as _extract_return_value,
)
from .canonicalizer import (
    _get_child_by_type as _get_child_by_type,
)
from .canonicalizer import (
    _get_source_text as _get_source_text,
)
from .canonicalizer import (
    _normalize_if_chain as _normalize_if_chain,
)
from .canonicalizer import (
    _semantic_node_type as _semantic_node_type,
)
from .canonicalizer import (
    ast_canonicalize as ast_canonicalize,
)
from .canonicalizer import (
    ast_canonicalize_with_identifiers as ast_canonicalize_with_identifiers,
)
from .canonicalizer import (
    canonicalize_full as canonicalize_full,
)
from .canonicalizer import (
    canonicalize_type4 as canonicalize_type4,
)
from .canonicalizer import (
    get_identifier_renames as get_identifier_renames,
)
from .canonicalizer import (
    normalize_identifiers as normalize_identifiers,
)
from .canonicalizer import (
    parse_file_once_from_string as parse_file_once_from_string,
)

__all__ = [
    "ast_canonicalize",
    "ast_canonicalize_with_identifiers",
    "canonicalize_full",
    "canonicalize_type4",
    "get_identifier_renames",
    "normalize_identifiers",
    "parse_file_once_from_string",
    "SEMANTIC_NODE_MAP",
    "_get_child_by_type",
    "_get_source_text",
    "_semantic_node_type",
    "_emit_canonical",
    "_emit_semantic_node",
    "_extract_return_value",
    "_normalize_if_chain",
]
