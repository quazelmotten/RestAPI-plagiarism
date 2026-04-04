"""Pipeline preparation: parsing, shadow lines, main block normalization."""

import logging

from ...fingerprinting.identifiers import _normalize_in_scope
from ..ast_helpers import _extract_main_block
from ..line_helpers import _make_shadow_lines

logger = logging.getLogger(__name__)


def prepare_sources(source_a, source_b, lang_code):
    lines_a = source_a.split("\n")
    lines_b = source_b.split("\n")
    try:
        from ...canonicalizer import parse_file_once_from_string

        tree_a, bytes_a = parse_file_once_from_string(source_a, lang_code)
        tree_b, bytes_b = parse_file_once_from_string(source_b, lang_code)
    except Exception:
        logger.warning(
            "Failed to parse sources (lang=%s), falling back to unoptimized path",
            lang_code,
            exc_info=True,
        )
        tree_a, bytes_a, tree_b, bytes_b = None, None, None, None
    shadow_a = _make_shadow_lines(source_a, lang_code, tree_a, bytes_a)
    shadow_b = _make_shadow_lines(source_b, lang_code, tree_b, bytes_b)
    if tree_a and tree_b:
        _apply_main_block_scope_normalization(
            lines_a, lines_b, shadow_a, shadow_b, tree_a, bytes_a, tree_b, bytes_b, lang_code
        )
    return lines_a, lines_b, tree_a, bytes_a, tree_b, bytes_b, shadow_a, shadow_b


def _apply_main_block_scope_normalization(
    lines_a, lines_b, shadow_a, shadow_b, tree_a, bytes_a, tree_b, bytes_b, lang_code
):
    main_a = _extract_main_block(tree_a.root_node, bytes_a, lang_code)
    main_b = _extract_main_block(tree_b.root_node, bytes_b, lang_code)
    if main_a and main_b:
        a_start = main_a["if_start_line"]
        a_end = main_a["end_line"]
        b_start = main_b["if_start_line"]
        b_end = main_b["end_line"]
        body_text_a = "\n".join(lines_a[a_start : a_end + 1])
        body_text_b = "\n".join(lines_b[b_start : b_end + 1])
        norm_a = _normalize_in_scope(body_text_a, lang_code).split("\n")
        norm_b = _normalize_in_scope(body_text_b, lang_code).split("\n")
        for k, line in enumerate(norm_a):
            idx = a_start + k
            if idx < len(shadow_a):
                shadow_a[idx] = line
        for k, line in enumerate(norm_b):
            idx = b_start + k
            if idx < len(shadow_b):
                shadow_b[idx] = line
