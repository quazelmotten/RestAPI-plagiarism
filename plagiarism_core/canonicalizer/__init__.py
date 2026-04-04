"""Code canonicalization for plagiarism type detection.

Provides two main capabilities:
1. Identifier normalization (Type 2 detection) - replaces variable/function names with placeholders
2. Semantic canonicalization (Type 4 detection) - normalizes known equivalent code patterns

The semantic canonicalization uses AST-based transformation (via tree-sitter) rather than
regex, ensuring correct handling of nested structures and proper convergence of
semantically equivalent code to the same canonical form.
"""

from .api import (
    ast_canonicalize as ast_canonicalize,
)
from .api import (
    ast_canonicalize_with_identifiers as ast_canonicalize_with_identifiers,
)
from .api import (
    canonicalize_full as canonicalize_full,
)
from .api import (
    canonicalize_type4 as canonicalize_type4,
)
from .api import (
    parse_file_once_from_string as parse_file_once_from_string,
)
from .ast_canonical import (
    _emit_canonical as _emit_canonical,
)
from .ast_canonical import (
    _emit_semantic_node as _emit_semantic_node,
)
from .ast_canonical import (
    _extract_return_value as _extract_return_value,
)
from .ast_canonical import (
    _normalize_if_chain as _normalize_if_chain,
)
from .identifier_norm import (
    _normalize_identifiers_from_tree as _normalize_identifiers_from_tree,
)
from .identifier_norm import (
    get_identifier_renames as get_identifier_renames,
)
from .identifier_norm import (
    normalize_identifiers as normalize_identifiers,
)
from .semantic_map import (
    SEMANTIC_NODE_MAP as SEMANTIC_NODE_MAP,
)
from .semantic_map import (
    _get_child_by_type as _get_child_by_type,
)
from .semantic_map import (
    _get_source_text as _get_source_text,
)
from .semantic_map import (
    _semantic_node_type as _semantic_node_type,
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
    "_normalize_identifiers_from_tree",
    "_normalize_if_chain",
]
