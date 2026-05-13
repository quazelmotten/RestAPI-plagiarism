"""Detection module — split from monolithic plagiarism_detector.py."""

from .ast_helpers import (
    _CLASS_NODE_TYPES,
    _FUNCTION_NODE_TYPES,
    _extract_functions,
    _extract_main_block,
    _extract_name,
    _FilteredNode,
    _hash_ast_subtree,
    _hash_ast_subtree_semantic,
    _is_main_block,
    _strip_self_from_params,
)
from .line_helpers import _line_hash, _make_exact_lines, _make_shadow_lines, _strip_comments
from .line_matcher import _extract_line_renames, _line_level_matches
from .semantic_line_matcher import _semantic_line_matches

__all__ = [
    # Line helpers
    "_strip_comments",
    "_make_shadow_lines",
    "_make_exact_lines",
    "_line_hash",
    # Line matcher
    "_line_level_matches",
    "_extract_line_renames",
    # AST helpers
    "_FilteredNode",
    "_strip_self_from_params",
    "_hash_ast_subtree",
    "_hash_ast_subtree_semantic",
    "_FUNCTION_NODE_TYPES",
    "_CLASS_NODE_TYPES",
    "_extract_name",
    "_extract_functions",
    "_is_main_block",
    "_extract_main_block",
    # Semantic line matcher
    "_semantic_line_matches",
]
