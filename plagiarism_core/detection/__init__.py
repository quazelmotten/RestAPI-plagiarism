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
from .body_signatures import (
    _extract_body_signature,
    _extract_comprehension_parts,
    _extract_comprehension_pattern,
    _extract_conditional_assign_signature,
    _extract_dict_pattern,
    _extract_lbyl_signature,
    _extract_loop_append_pattern,
    _extract_map_lambda_parts,
    _extract_nested_if_signature,
    _extract_return_chain_signature,
    _extract_return_value,
    _extract_ternary_signature,
    _extract_try_signature,
    _extract_tuple_return_signature,
)
from .function_matcher import _function_level_matches
from .keywords import _LANGUAGE_KEYWORDS, _get_keywords_for_language
from .line_helpers import _line_hash, _make_exact_lines, _make_shadow_lines, _strip_comments
from .line_matcher import _extract_line_renames, _line_level_matches
from .merge_helpers import _covered_lines, _merge_matches
from .pipeline import detect_plagiarism, detect_plagiarism_from_files
from .semantic_function_matcher import _semantic_function_matches
from .semantic_line_matcher import _semantic_line_matches

__all__ = [
    # Pipeline
    "detect_plagiarism",
    "detect_plagiarism_from_files",
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
    # Function matcher
    "_function_level_matches",
    # Semantic line matcher
    "_semantic_line_matches",
    # Semantic function matcher
    "_semantic_function_matches",
    # Merge helpers
    "_merge_matches",
    "_covered_lines",
    # Body signatures
    "_extract_comprehension_pattern",
    "_extract_comprehension_parts",
    "_extract_loop_append_pattern",
    "_extract_return_value",
    "_extract_map_lambda_parts",
    "_extract_conditional_assign_signature",
    "_extract_nested_if_signature",
    "_extract_tuple_return_signature",
    "_extract_return_chain_signature",
    "_extract_body_signature",
    "_extract_ternary_signature",
    "_extract_dict_pattern",
    "_extract_try_signature",
    "_extract_lbyl_signature",
    # Keywords
    "_LANGUAGE_KEYWORDS",
    "_get_keywords_for_language",
]
